import logging
import asyncio
import json
import time
from pathlib import Path
from typing import Literal, Optional, Sequence, Tuple

from sqlmodel import Session, select
from sqlalchemy.exc import InterfaceError, OperationalError

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_endpoints import MessageLog
from app.models_identifiers import Identifier, IdentifierType
from app.models_structure import IdentifierNamespace
from app.services.fhir_emission import emit_fhir_payload, generate_fhir
# REMARQUE: do NOT import network senders at module import time. Tests use monkeypatch
# to replace the functions on their modules (app.services.mllp, app.services.fhir_transport).
# Import them dynamically at call-site so monkeypatching the module attributes works.
from app.services.pam_profile_fr import format_xtn, normalize_generated_message
from app.services.identifier_manager import map_identifier_type_to_hl7_code
from app.services.pam_emission import (
    emit_outbound_pam_attempt,
    validate_outbound_pam,
)
from app.services.emission_endpoints import list_eligible_sender_endpoints
from app.services.hprim_emission import emit_hprim_act

logger = logging.getLogger(__name__)


# Helper pour retry des requêtes SQLite en cas d'erreur de concurrence
def _safe_query(session: Session, statement, max_retries=3):
    """Execute query with retry logic for SQLite concurrency errors."""
    for attempt in range(max_retries):
        try:
            return session.exec(statement).first()
        except (InterfaceError, OperationalError) as e:
            if "out of sequence" in str(e) or "database is locked" in str(e):
                if attempt < max_retries - 1:
                    time.sleep(0.05 * (attempt + 1))  # Backoff exponentiel
                    session.rollback()  # Réinitialiser la session
                    continue
            logger.warning(f"SQLite concurrency error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None
    return None


# Global sanitization helper: coerce None / 'None' / whitespace-only to ''
def _c(val):
    logger.debug(f"_c called with val={val}")
    if val is None:
        return ""
    if isinstance(val, str):
        v = val.strip()
        if v.lower() == "none" or v == "":
            return ""
        return v
    return str(val)


def _normalize_mrg_prior_identifiers(identifiers: Optional[Sequence[object]]) -> list[str]:
    """Normalise les répétitions CX destinées à MRG-1.

    La frontière d'émission refuse ainsi une liste vide (ou seulement composée
    de séparateurs ``~``) avant de construire un A40/A47 impossible à appliquer.
    """
    normalized = [
        repetition.strip()
        for value in identifiers or []
        for repetition in str(value or "").split("~")
        if repetition.strip()
    ]
    if any("|" in value or "\r" in value or "\n" in value for value in normalized):
        raise ValueError("MRG-1 doit contenir des identifiants CX sans séparateur de segment ou de champ")
    return normalized


def _new_message_control_id(seed: object) -> str:
    """Construit un MSH-10 unique sans altérer les identifiants métier.

    Un même patient ou mouvement peut être émis plusieurs fois. Réutiliser son
    ID interne comme MSH-10 déclenche l'idempotence du récepteur et provoque la
    perte silencieuse des mises à jour ultérieures.
    """
    from uuid import uuid4

    return f"{seed}-{uuid4().hex[:12]}"


def build_pid3_identifiers(
    patient: Patient,
    session: Session,
    forced_system: str | None = None,
    forced_oid: str | None = None,
) -> str:
    def _auth(system: str | None, oid: str | None) -> str:
        system = (system or "").strip()
        oid = (oid or "").strip()
        return f"{system}&{oid}&ISO" if system and oid else system

    identifiers = []
    logger.info(f"build_pid3_identifiers called with args: {locals()}")

    # Support both model instances and snapshot dicts
    is_dict = isinstance(patient, dict)

    def _get(attr, default=None):
        return (patient.get(attr, default) if is_dict else getattr(patient, attr, default))

    # L'identifiant métier porté par Patient.identifier est celui qui a servi à
    # résoudre le patient à l'entrée (souvent l'IPP du partenaire). Il doit
    # figurer en première répétition de PID-3 : le récepteur l'utilise comme
    # identifiant principal. L'identifiant technique local est ajouté ensuite.
    # L'ordre inverse cassait un roundtrip inter-GHT en faisant de l'ID local
    # de l'émetteur l'identifiant principal du destinataire.
    primary_identifier_value = _c(_get("identifier", None))
    if primary_identifier_value:
        primary_identifier = None
        try:
            patient_id = _get("id")
            if patient_id:
                primary_identifier = _safe_query(
                    session,
                    select(Identifier)
                    .where(Identifier.patient_id == patient_id)
                    .where(Identifier.value == primary_identifier_value)
                    .where(Identifier.status == "active"),
                )
        except Exception:
            logger.exception("Error resolving the primary PID-3 identifier")
        if primary_identifier:
            authority = _auth(primary_identifier.system, getattr(primary_identifier, "oid", None))
            type_code = map_identifier_type_to_hl7_code(primary_identifier.type)
            identifiers.append(f"{primary_identifier_value}^^^{authority}^{type_code}")
        else:
            authority = _auth(forced_system, forced_oid) or "HOSP"
            identifiers.append(f"{primary_identifier_value}^^^{authority}^PI")

    # Priority: include internal IPP identifier (patient_seq or id) using IdentifierNamespace of type 'IPP' when available
    internal_identifier_value = None
    try:
        internal_id_val = _get("patient_seq") or _get("id")
        # Ne pas ajouter un second identifiant technique quand PID-3 porte
        # déjà l'identifiant métier. Sinon un destinataire qui connaît notre
        # namespace local peut sélectionner ce second identifiant comme
        # principal, malgré l'ordre de PID-3, et rompre la conservation d'IPP.
        if internal_id_val and not primary_identifier_value:
            ipp_ns = None
            ej_id = _get('entite_juridique_id')
            if ej_id:
                ipp_ns = _safe_query(
                    session,
                    select(IdentifierNamespace)
                    .where(IdentifierNamespace.entite_juridique_id == ej_id)
                    .where(IdentifierNamespace.type == "IPP")
                    .where(IdentifierNamespace.is_active.is_(True))
                )
            auth = None
            if ipp_ns:
                auth = _auth(ipp_ns.system, ipp_ns.oid)
            elif forced_system or forced_oid:
                auth = _auth(forced_system, forced_oid)
            if auth:
                internal_identifier_value = _c(str(internal_id_val))
                identifiers.append(f"{internal_identifier_value}^^^{auth}^PI")
    except Exception:
        logger.exception("Error while resolving IPP namespace for internal identifier")

    # 2. External ID si présent - chercher dans Identifier pour avoir system/oid
    external_id_clean = _c(_get("external_id", None))
    if external_id_clean:  # Only add if not empty after sanitization
        # Chercher si cet external_id est dans la table Identifier
        pid = _get('id')
        ext_ident = _safe_query(
            session,
            select(Identifier)
            .where(Identifier.patient_id == pid)
            .where(Identifier.value == external_id_clean)
            .where(Identifier.status == "active")
        )
        if ext_ident:
            ident_type = map_identifier_type_to_hl7_code(ext_ident.type)
            identifiers.append(
                f"{_c(ext_ident.value)}^^^{_auth(ext_ident.system, ext_ident.oid)}^{ident_type}"
            )
        else:
            identifiers.append(f"{external_id_clean}^^^{_auth('EXTERNAL', None)}^PI")

    # 3. INS/NIR : l'identifiant national est déclaré avec son autorité et le
    # type INS (et non NH, réservé à un ancien codage local).
    nir_clean = _c(_get("nir", None))
    if nir_clean:
        identifiers.append(f"{nir_clean}^^^ASIP-SANTE&1.2.250.1.213.1.4.8&ISO^INS")

    # 4. Tous les autres identifiants actifs
    already_added_values = set()
    pid_val = _get('id')
    if pid_val:
        already_added_values.add(str(pid_val))
    if internal_identifier_value:
        already_added_values.add(internal_identifier_value)
    if primary_identifier_value:
        already_added_values.add(primary_identifier_value)
    ext_val = _get('external_id')
    if ext_val:
        already_added_values.add(ext_val)
    nir_val = _get('nir')
    if nir_val:
        already_added_values.add(nir_val)

    # Load identifiers from DB if we have a model (or if snapshot didn't include identifiers)
    id_list = None
    if is_dict:
        id_list = patient.get('identifiers') or []
    else:
        if not getattr(patient, 'identifiers', None):
            id_list = session.exec(select(Identifier).where(Identifier.patient_id == pid_val)).all()
        else:
            id_list = getattr(patient, 'identifiers')

    for ident in id_list or []:
        # ident may be dict (from snapshot) or model
        if isinstance(ident, dict):
            status = ident.get('status')
            value = ident.get('value')
            system = ident.get('system')
            oid = ident.get('oid')
            typ = ident.get('type')
        else:
            status = getattr(ident, 'status', None)
            value = getattr(ident, 'value', None)
            system = getattr(ident, 'system', None)
            oid = getattr(ident, 'oid', None)
            typ = getattr(ident, 'type', None)
        if status == 'active' and value not in already_added_values:
            identifiers.append(f"{_c(value)}^^^{_auth(system, oid)}^{map_identifier_type_to_hl7_code(typ)}")
            already_added_values.add(_c(value))

    # As a last resort, ensure PID-3 is populated with an internal identifier so PAM validators accept the payload.
    if not identifiers:
        try:
            fallback_val = _get("patient_seq") or _get("id")
            if fallback_val:
                auth = _auth(forced_system, forced_oid) or "HOSP"
                internal_identifier_value = _c(str(fallback_val))
                identifiers.append(f"{internal_identifier_value}^^^{auth}^PI")
        except Exception:
            logger.exception("Failed to build fallback PID-3 identifier")

    return "~".join(identifiers) if identifiers else ""


def _snapshot_entity(entity, entity_type: str, session: Session) -> dict:
    """Create a plain dict snapshot for the given entity to avoid lazy loads.
    Only include commonly used scalar fields and relation ids used by generators.
    This keeps emission code free of session-bound lazy-loading and safe to run
    after the SQL row is deleted (when appropriate).
    """
    s = {}
    try:
        if entity_type == 'patient':
            s.update({
                'id': getattr(entity, 'id', None),
                'patient_seq': getattr(entity, 'patient_seq', None),
                'family': getattr(entity, 'family', None),
                'given': getattr(entity, 'given', None),
                'gender': getattr(entity, 'gender', None),
                'birth_date': getattr(entity, 'birth_date', None),
                'external_id': getattr(entity, 'external_id', None),
                'nir': getattr(entity, 'nir', None),
                'entite_juridique_id': getattr(entity, 'entite_juridique_id', None),
            })
            # identifiers: materialize into list of dicts
            idents = []
            try:
                id_objs = getattr(entity, 'identifiers', None)
                if not id_objs:
                    id_objs = session.exec(select(Identifier).where(Identifier.patient_id == getattr(entity, 'id', None))).all()
                for ii in id_objs or []:
                    idents.append({'value': ii.value, 'system': ii.system, 'oid': getattr(ii, 'oid', None), 'status': ii.status, 'type': getattr(ii, 'type', None)})
            except Exception:
                idents = []
            s['identifiers'] = idents
        elif entity_type == 'dossier':
            s.update({
                'id': getattr(entity, 'id', None),
                'dossier_seq': getattr(entity, 'dossier_seq', None),
                'patient_id': getattr(entity, 'patient_id', None),
                'entite_juridique_id': getattr(entity, 'entite_juridique_id', None),
                'dossier_type': getattr(entity, 'dossier_type', None),
                'uf_responsabilite': getattr(entity, 'uf_responsabilite', None),
            })
        elif entity_type == 'venue':
            s.update({
                'id': getattr(entity, 'id', None),
                'venue_seq': getattr(entity, 'venue_seq', None),
                'dossier_id': getattr(entity, 'dossier_id', None),
                'start_time': getattr(entity, 'start_time', None),
                'uf_responsabilite': getattr(entity, 'uf_responsabilite', None),
            })
        elif entity_type == 'mouvement':
            s.update({
                'id': getattr(entity, 'id', None),
                'mouvement_seq': getattr(entity, 'mouvement_seq', None),
                'venue_id': getattr(entity, 'venue_id', None),
                'when': getattr(entity, 'when', None),
                'type': getattr(entity, 'type', None),
                'trigger_event': getattr(entity, 'trigger_event', None),
                'uf_responsabilite': getattr(entity, 'uf_responsabilite', None),
                'location': getattr(entity, 'location', None),
            })
        else:
            s.update({k: getattr(entity, k, None) for k in dir(entity) if not k.startswith('_')})
    except Exception:
        logger.exception("Failed to snapshot entity %s", entity)
    return s


def _resolve_namespace_authority(
    session: Session, entite_juridique_id: int | None, ns_type: str, forced_system: str | None = None, forced_oid: str | None = None
) -> Tuple[str, str]:
    """Return (authority, type_code) for a namespace of given type.
    authority is formatted as 'system&oid&ISO' when both present, or system when only system present.
    type_code is the namespace.type (e.g. 'IPP','NDA','VN','MVT').
    Falls back to forced_system/forced_oid or ('HOSP', ns_type).
    """
    def _auth(system: str | None, oid: str | None) -> str:
        system = (system or "").strip()
        oid = (oid or "").strip()
        return f"{system}&{oid}&ISO" if system and oid else system or ""

    if entite_juridique_id:
        try:
            ns = session.exec(
                select(IdentifierNamespace)
                .where(IdentifierNamespace.entite_juridique_id == entite_juridique_id)
                .where(IdentifierNamespace.type == ns_type)
                .where(IdentifierNamespace.is_active.is_(True))
            ).first()
            if ns:
                return (_auth(ns.system, ns.oid), ns.type or ns_type)
        except Exception:
            logger.exception("Error resolving IdentifierNamespace for type %s and ej=%s", ns_type, entite_juridique_id)

    # Solution de repli to forced values or defaults
    auth = _auth(forced_system, forced_oid) or (forced_system or "HOSP")
    return (auth, ns_type)


def generate_pam_hl7(
    entity,
    entity_type: Literal["patient", "dossier", "venue", "mouvement"],
    session: Session,
    forced_identifier_system: str | None = None,
    forced_identifier_oid: str | None = None,
    operation: str = "insert",
    msh_sending_app: str | None = None,
    msh_sending_facility: str | None = None,
    msh_receiving_app: str | None = None,
    msh_receiving_facility: str | None = None,
    mrg_prior_identifiers: Optional[list] = None,
    mrg_prior_name: str | None = None,
) -> str:
    logger.info(f"generate_pam_hl7 called with args: {locals()}")
    """Build a minimal HL7 PAM message for the given entity type.

    This function accepts either SQLModel instances or the snapshot dict produced
    by `_snapshot_entity`. It uses local accessors to read attributes safely.
    """

    # Support snapshots (plain dicts) or model instances
    is_dict = isinstance(entity, dict)

    def _get(attr, default=None):
        return (entity.get(attr, default) if is_dict else getattr(entity, attr, default))

    def _c_local(v):
        # reuse outer _c sanitizer
        return _c(v)

    # Reusable XPN builder for all branches (family^given^middle^suffix^prefix^degree^type)
    def _build_xpn(family_val, given_val, middle_val=None, suffix_val=None, prefix_val=None, type_code=None):
        xpn = ["", "", "", "", "", "", ""]
        if family_val:
            xpn[0] = family_val
        if given_val:
            xpn[1] = given_val
        if middle_val:
            xpn[2] = middle_val
        if suffix_val:
            xpn[3] = suffix_val
        if prefix_val:
            xpn[4] = prefix_val
        if type_code:
            xpn[6] = type_code
        # Trim trailing empty components
        while xpn and xpn[-1] == "":
            xpn.pop()
        return "^".join(xpn)

    def _build_patient_name(family_val, given_val, middle_val, suffix_val, prefix_val, birth_family_val):
        """Construit PID-5 sans dupliquer un nom légal identique au nom courant."""
        birth_family_val = _c_local(birth_family_val) or None
        is_legal_name = bool(birth_family_val and birth_family_val == family_val)
        current_type = "L" if is_legal_name else "D" if birth_family_val else None
        names = []
        if family_val or given_val or middle_val or prefix_val or suffix_val:
            names.append(
                _build_xpn(
                    family_val, given_val, middle_val, suffix_val, prefix_val, current_type
                )
            )
        if birth_family_val and not is_legal_name:
            names.append(
                _build_xpn(
                    birth_family_val, given_val, middle_val, suffix_val, prefix_val, "L"
                )
            )
        return "~".join(names)

    # Patient HL7 PAM branch
    if entity_type == "patient":
        # Determine event type
        if operation == "merge":
            event_type = "A40"
        elif operation == "change_id":
            event_type = "A47"
        else:
            event_type = "A31" if operation == "update" else "A28"

        normalized_mrg_prior_identifiers = _normalize_mrg_prior_identifiers(mrg_prior_identifiers)
        if event_type in {"A40", "A47"} and not normalized_mrg_prior_identifiers:
            raise ValueError(
                f"ADT^{event_type} requiert au moins un identifiant antérieur dans MRG-1"
            )
        if event_type == "A40" and mrg_prior_name and any(
            character in str(mrg_prior_name) for character in "|\r\n"
        ):
            raise ValueError("MRG-7 ne doit pas contenir de séparateur de segment ou de champ")

        # Build timestamp and control id
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        control_id = _new_message_control_id(_get("patient_seq", _get("id", "UNKNOWN")))

        # MSH header
        if event_type == "A40":
            msg_structure = "ADT_A39"
        elif event_type == "A47":
            msg_structure = "ADT_A30"
        else:
            msg_structure = "ADT_A05"
        sending_app = msh_sending_app or "POC"
        sending_fac = msh_sending_facility or "HOSP"
        receiving_app = msh_receiving_app or "EXT"
        receiving_fac = msh_receiving_facility or "HOSP"
        msh = f"MSH|^~\\&|{sending_app}|{sending_fac}|{receiving_app}|{receiving_fac}|{timestamp}||ADT^{event_type}^{msg_structure}|{control_id}|P|2.5^FRA^2.11|||||FRA|8859/1"
        evn = f"EVN|{event_type}|{timestamp}"

        # PID-3 identifiers
        pid3 = build_pid3_identifiers(entity, session, forced_system=forced_identifier_system, forced_oid=forced_identifier_oid)


        family = _c_local(_get("family", ""))
        given = _c_local(_get("given", ""))
        middle = _c_local(_get("middle", None))
        suffix = _c_local(_get("suffix", None)) or None
        prefix = _c_local(_get("prefix", None)) or None
        birth_family = _c_local(_get("birth_family", None)) or None
        name = _build_patient_name(
            family, given, middle, suffix, prefix, birth_family
        )

        # Birth date
        birth_date_raw = _c_local(_get("birth_date", ""))
        birth_date = birth_date_raw.replace("-", "").replace("/", "")[:8] if birth_date_raw else ""

        # Gender mapping — PID-8 (Sexe) : l'extension nationale IHE FR restreint les valeurs
        # permises à F/M/U (table HL7 0001), pas de code "O" ; "other" est donc mappé sur "U".
        raw_gender = _c_local(_get("gender", ""))
        gender_map_hl7 = {
            "m": "M", "male": "M",
            "f": "F", "female": "F",
            "o": "U", "other": "U",
            "u": "U", "unknown": "U", "undifferentiated": "U", "n": "U"
        }
        gender = gender_map_hl7.get(raw_gender.lower(), raw_gender.upper()) if raw_gender else ""

        # Addresses
        # Addresses: build XAD repetitions but only include repetitions with meaningful content
        def _build_xad(street, other, city, state, postal, country, addr_type=None):
            parts = [street or "", other or "", city or "", state or "", postal or "", country or ""]
            if addr_type:
                parts.append(addr_type)
            # Trim trailing empty components
            while parts and parts[-1] == "":
                parts.pop()
            return "^".join(parts) if parts else ""

        addresses = []
        street = _c_local(_get("address", None))
        city = _c_local(_get("city", None))
        state = _c_local(_get("state", None))
        postal = _c_local(_get("postal_code", None))
        country = _c_local(_get("country", None))
        # Only add home address repetition if at least one meaningful field exists
        if any([street, city, state, postal, country]):
            addresses.append(_build_xad(street, "", city, state, postal, country, "H"))

        birth_street = _c_local(_get("birth_address", None))
        birth_city = _c_local(_get("birth_city", None))
        birth_state = _c_local(_get("birth_state", None))
        birth_postal = _c_local(_get("birth_postal_code", None))
        birth_country = _c_local(_get("birth_country", None))
        if any([birth_street, birth_city, birth_state, birth_postal, birth_country]):
            addresses.append(_build_xad(birth_street, "", birth_city, birth_state, birth_postal, birth_country, "BIR"))

        patient_address = "~".join(addresses)

        # Phones
        phones = []
        phone = _c_local(_get("phone", ""))
        if phone:
            phones.append(format_xtn(number=phone, use="PRN", equipment="PH"))
        mobile = _c_local(_get("mobile", ""))
        if mobile:
            phones.append(format_xtn(number=mobile, use="ORN", equipment="CP"))
        work_phone = _c_local(_get("work_phone", ""))
        if work_phone:
            phones.append(format_xtn(number=work_phone, use="WPN", equipment="PH"))
        email = _c_local(_get("email", ""))
        if email:
            phones.append(format_xtn(use="NET", equipment="Internet", email=email))
        phone_field = "~".join(phones)

        birth_place = _c_local(_get("birth_city", ""))
        marital_status = _c_local(_get("marital_status", ""))
        nationality = _c_local(_get("nationality", ""))
        identity_code = _c_local(_get("identity_reliability_code", ""))
        # Attempt to include account_number (PID-18) if there's a dossier for this patient
        account_number = ""
        try:
            pid_patient_id = _get('id', None)
            if pid_patient_id is not None:
                # pick latest dossier for this patient if any
                from sqlmodel import select as _select
                dossier_obj = session.exec(_select(Dossier).where(Dossier.patient_id == pid_patient_id).order_by(Dossier.id.desc())).first()
                if dossier_obj and getattr(dossier_obj, 'dossier_seq', None):
                    # resolve namespace authority for NDA (dossier numbers)
                    auth, type_code = _resolve_namespace_authority(
                        session,
                        _get('entite_juridique_id'),
                        'NDA',
                        forced_identifier_system,
                        forced_identifier_oid,
                    )
                    type_code = type_code or 'AN'
                    if auth:
                        account_number = f"{_c_local(str(dossier_obj.dossier_seq))}^^^{auth}^{type_code}"
                    else:
                        account_number = f"{_c_local(str(dossier_obj.dossier_seq))}^^^{_c_local('HOSP')}^{type_code}"
        except Exception:
            logger.exception("Failed to resolve dossier/account_number for PID-18")

        if not account_number:
            # Fallback: reuse patient sequence/id so PID-18 is never empty (IHE requires it)
            fallback_value = _c_local(str(_get('patient_seq') or _get('id') or 'PENDING'))
            fallback_auth, fallback_type = _resolve_namespace_authority(
                session,
                _get('entite_juridique_id'),
                'NDA',
                forced_identifier_system,
                forced_identifier_oid,
            )
            fallback_type = fallback_type or 'AN'
            fallback_auth = fallback_auth or _c_local('HOSP')
            account_number = f"{fallback_value}^^^{fallback_auth}^{fallback_type}"

        # Build PID using indexed fields to ensure PID-18 (account number) and PID-23 (birth place)
        # are placed at their correct positions.
        # We allocate up to PID-32 for safety (index matches HL7 field number).
        pid_fields = [""] * 33
        pid_fields[0] = "PID"
        pid_fields[1] = "1"  # Set ID - PID-1
        pid_fields[2] = ""   # PID-2 (Patient ID)
        pid_fields[3] = _c_local(pid3)  # PID-3 Patient Identifier List
        pid_fields[4] = ""   # PID-4 Alternate ID
        pid_fields[5] = _c_local(name)  # PID-5 Patient Name
        pid_fields[6] = ""   # PID-6 Mother's Maiden Name
        pid_fields[7] = birth_date  # PID-7 Date/Time of Birth
        pid_fields[8] = gender  # PID-8 Administrative Sex
        pid_fields[9] = ""   # PID-9 Patient Alias
        pid_fields[10] = ""  # PID-10 Race
        pid_fields[11] = _c_local(patient_address)  # PID-11 Patient Address
        pid_fields[12] = ""  # PID-12 County Code
        pid_fields[13] = phone_field  # PID-13 Phone Number - Home
        pid_fields[14] = ""  # PID-14 Phone Number - Business
        pid_fields[15] = ""  # PID-15 Primary Language
        pid_fields[16] = _c_local(marital_status)  # PID-16 Marital Status
        pid_fields[17] = ""  # PID-17 Religion
        pid_fields[18] = _c_local(account_number)  # PID-18 Patient Account Number
        # PID-19.. PID-22 left empty for now
        pid_fields[19] = ""  # PID-19 SSN Number - Patient
        pid_fields[20] = ""  # PID-20 Driver's License Number
        pid_fields[21] = ""  # PID-21 Mother's Identifier
        pid_fields[22] = ""  # PID-22 Ethnic Group
        pid_fields[23] = _c_local(birth_place)  # PID-23 Birth Place
        pid_fields[24] = ""  # PID-24 Mother's Maiden Name (repeating semantics)
        # PID-25..PID-31 reserved
        pid_fields[32] = _c_local(identity_code)  # PID-32 Identity Reliability Code

        pid = "|".join(pid_fields)

        # Minimal PV1 so validators always find visit data even when no dossier/venue exists yet
        visit_number_value = _c_local(str(_get('patient_seq') or _get('id') or '0'))
        vn_auth, vn_type = _resolve_namespace_authority(
            session,
            _get('entite_juridique_id'),
            'VN',
            forced_identifier_system,
            forced_identifier_oid,
        )
        vn_auth = vn_auth or _c_local('HOSP')
        vn_type = vn_type or 'VN'
        pv1_fields = [""] * 40
        pv1_fields[0] = "PV1"
        pv1_fields[1] = "1"
        pv1_fields[2] = "O"  # Default patient class (Outpatient) for standalone patient events
        pv1_fields[3] = ""   # Location unknown at this stage
        pv1_fields[19] = f"{visit_number_value}^^^{vn_auth}^{vn_type}"
        pv1 = "|".join(pv1_fields)

        if event_type in ("A40", "A47"):
            # A40 (fusion) / A47 (modification d'identifiant) : MRG-1 porte le/les identifiant(s)
            # obsolète(s) (répétable via ~), PID-3 porte déjà le/les identifiant(s) retenu(s).
            # Conforme à l'exemple de la spec IHE PAM France (§4.4.2) : MSH, EVN, PID, MRG (pas de PV1).
            mrg_fields = [""] * 8
            mrg_fields[0] = "MRG"
            mrg_fields[1] = "~".join(_c_local(p) for p in normalized_mrg_prior_identifiers)
            if mrg_prior_name:
                mrg_fields[7] = _c_local(mrg_prior_name)
            mrg = "|".join(mrg_fields)
            return normalize_generated_message("\r".join([msh, evn, pid, mrg]))

        return normalize_generated_message("\r".join([msh, evn, pid, pv1]))
        
    if entity_type == "dossier":
        # ⚠️ IMPORTANT : La création d'un dossier ne génère PAS de message IHE PAM
        # car il n'y a pas d'événement patient associé. C'est la création de la VENUE
        # (admission/pre-admit) qui générera le message ADT^A05.
        # En FHIR : Dossier = EpisodeOfCare, Venue = Encounter
        return None  # Pas de message généré pour un dossier seul
    
    if entity_type == "venue":
        # Création = ADT^A05^ADT_A01, modification = ADT^Z99^ADT_Z99
        if operation == "insert":
            event_type = "A05"
            msg_structure = "ADT_A05"
        else:
            event_type = "Z99"
            msg_structure = "ADT_A01"
        assigning_system = forced_identifier_system or "HOSP"
        assigning_oid = forced_identifier_oid

        dossier = entity.dossier if hasattr(entity, "dossier") else None
        patient = dossier.patient if dossier and hasattr(dossier, "patient") else None
        if not dossier:
            return None

        # Patient info
        if patient:
            patient_seq_val = getattr(patient, "patient_seq", None) or (patient.id or "TEMP")
            patient_id = patient.identifier or str(patient_seq_val)
            family = patient.family or ""
            given = patient.given or ""
            if patient.birth_date:
                if hasattr(patient.birth_date, 'strftime'):
                    birth_date = patient.birth_date.strftime("%Y%m%d")
                else:
                    birth_date = str(patient.birth_date).replace("-", "")
            else:
                birth_date = ""
            raw_gender = (patient.gender or "").strip()
            # PID-8 : l'extension nationale IHE FR restreint les valeurs permises à F/M/U
            # (table HL7 0001) ; pas de code "O", "other" est donc mappé sur "U".
            gender_map_hl7 = {
                "m": "M", "male": "M",
                "f": "F", "female": "F",
                "o": "U", "other": "U",
                "u": "U", "unknown": "U", "undifferentiated": "U", "n": "U"
            }
            gender = gender_map_hl7.get(raw_gender.lower(), raw_gender.upper()) if raw_gender else ""
        else:
            patient_id = str(dossier.patient_id)
            family = ""
            given = ""
            birth_date = ""
            gender = ""

        admit_time = entity.start_time.strftime("%Y%m%d%H%M%S") if entity.start_time else ""
        control_id = _new_message_control_id(entity.venue_seq)
        visit_number = str(dossier.dossier_seq)
        authority = f"{assigning_system}&{assigning_oid}&ISO" if assigning_oid else assigning_system
        pid3 = f"{patient_id}^^^{authority}^PI"
        pid18 = f"{visit_number}^^^{authority}^AN"

        msh = f"MSH|^~\\&|POC|HOSP|EXT|HOSP|{admit_time}||ADT^{event_type}^{msg_structure}|{control_id}|P|2.5^FRA^2.11|||||FRA|8859/1"
        evn = f"EVN|{event_type}|{admit_time}"

        # PID-5 keeps the current and birth names in separate XPN repetitions.
        name_field = _build_patient_name(
            family,
            given,
            getattr(patient, "middle", None) if patient else None,
            getattr(patient, "suffix", None) if patient else None,
            getattr(patient, "prefix", None) if patient else None,
            getattr(patient, "birth_family", None) if patient else None,
        )

        pid_fields = [
            "PID", "1", "", pid3, "", _c_local(name_field), "", birth_date, gender
        ]
        while len(pid_fields) < 19:
            pid_fields.append("")
        pid_fields[18] = pid18

        if patient:
            addr = []
            addr.append(patient.address or "")
            addr.append("")
            addr.append(patient.city or "")
            addr.append(patient.state or "")
            addr.append(patient.postal_code or "")
            addr.append(patient.country or "")
            addr.append("H")
            pid_fields[11] = "^".join(addr)
            xtn_parts = []
            if getattr(patient, "phone", None):
                xtn_parts.append(format_xtn(number=patient.phone, use="PRN", equipment="PH"))
            if getattr(patient, "mobile", None):
                xtn_parts.append(format_xtn(number=patient.mobile, use="ORN", equipment="CP"))
            if getattr(patient, "email", None):
                xtn_parts.append(format_xtn(use="NET", equipment="Internet", email=patient.email))
            if xtn_parts:
                pid_fields[13] = "~".join(xtn_parts)

        pid = "|".join(pid_fields)

        from app.services.vocabulary_translate import map_code
        dossier_type_val = getattr(dossier, "dossier_type", None)
        if hasattr(dossier_type_val, "value"):
            dossier_type_val = dossier_type_val.value
        encounter_class = str(dossier_type_val) if dossier_type_val else "IMP"
        patient_class = map_code(
            session,
            source_system_name="encounter-class",
            source_code=encounter_class,
            target_system_name="patient-class"
        )
        if not patient_class:
            patient_class_map = {"hospitalise": "I", "externe": "O", "urgence": "E", "IMP": "I", "AMB": "O", "EMER": "E"}
            patient_class = patient_class_map.get(encounter_class, "I")

        location = entity.uf_responsabilite or ""
        admission_type = getattr(dossier, "admission_type", "") or ""
        attending = getattr(entity, "attending_provider", None) or getattr(dossier, "attending_provider", "") or ""
        hospital_service = getattr(entity, "hospital_service", "") or ""
        admit_source = getattr(dossier, "admission_source", "") or ""
        pv1_19 = f"{visit_number}^^^{authority}^VN"
        pv1 = (
            f"PV1|1|{patient_class}|{location}|{admission_type}|||{attending}|||{hospital_service}||||{admit_source}|||||{pv1_19}"
            f"|||||||||||||||||||||||||{admit_time}"
        )

        zbe_id = str(entity.venue_seq)
        action = "INSERT"
        historic = "N"
        # ZBE-7: UF médicale = UF de responsabilité (XON format: label^code^code_type^^^id^^^id_type^assigning_authority^component10=code)
        uf_responsabilite = getattr(entity, "uf_responsabilite", None) or getattr(dossier, "uf_responsabilite", None) or ""
        # XON format: name (1) ^ code (2) ^ type (3) ^ ... ^ code (10)
        # We need at least component 10 filled with the code
        if uf_responsabilite:
            zbe_7_comps = [""] * 10
            zbe_7_comps[0] = uf_responsabilite  # Component 1: label/code
            zbe_7_comps[9] = uf_responsabilite  # Component 10: code
            zbe_7 = "^".join(zbe_7_comps)
        else:
            zbe_7 = ""
        # ZBE-8: UF de soins (XON format - same as ZBE-7)
        uf_soins_code = getattr(entity, "uf_soins_code", None) or getattr(dossier, "uf_soins_code", None) or ""
        uf_soins_label = getattr(entity, "uf_soins_label", None) or getattr(dossier, "uf_soins_label", None) or ""
        if uf_soins_code:
            zbe_8_comps = [""] * 10
            zbe_8_comps[0] = uf_soins_label  # Component 1: label
            zbe_8_comps[9] = uf_soins_code  # Component 10: code
            zbe_8 = "^".join(zbe_8_comps)
        else:
            zbe_8 = ""
        # ZBE-9: nature du mouvement (S,H,M,L,D,SM)
        from app.services.nature_mapping import derive_nature
        nature = getattr(entity, "nature", None)
        zbe_9 = derive_nature(event_type, nature)
        valid_natures = {"S", "H", "M", "L", "D", "SM", "SH", "MH", "LD", "HMS", "C"}
        if not zbe_9 or zbe_9 not in valid_natures:
            zbe_9 = "H"  # Default to hospitalisation
        # ZBE for A05 (venue creation): no ZBE-6 for INSERT
        zbe = f"ZBE|{zbe_id}|{admit_time}||{action}|{historic}||{zbe_7}|{zbe_8}|{zbe_9}"

        return normalize_generated_message("\r".join([msh, evn, pid, pv1, zbe]))
    if entity_type == "mouvement":
        # Utiliser le mapping métier <-> HL7 pour déterminer le code HL7 à partir du type métier
        from app.movement_type_mapping import to_standard_movement_code
        
        # Helper function to detect A06/A07 based on movement history
        def detect_a06_a07_from_history(entity, session, operation):
            """
            Detect A06 or A07 based on venue movement history.
            - A06: Outpatient → Inpatient (S → H)
            - A07: Inpatient → Outpatient (H → S)
            Returns: ("A06"|"A07|None, previous_nature)
            """
            # Only consider detection for new insert movements
            if operation != "insert":
                return None, None
            if not getattr(entity, "venue_id", None):
                return None, None
            current_nature = getattr(entity, "nature", None)
            if not current_nature or current_nature not in ["H", "S"]:
                return None, None

            previous_movements = session.exec(
                select(Mouvement)
                .where(Mouvement.venue_id == entity.venue_id)
                .where(Mouvement.when < entity.when)
                .order_by(Mouvement.when.desc())
            ).all()
            if not previous_movements:
                return None, None
            last_nature = None
            for prev in previous_movements:
                if getattr(prev, "nature", None) in ["H", "S"]:
                    last_nature = getattr(prev, "nature")
                    break
            if not last_nature:
                return None, None
            if last_nature == "S" and current_nature == "H":
                return "A06", last_nature
            if last_nature == "H" and current_nature == "S":
                return "A07", last_nature
            return None, None

        # Priority 1: Use explicit trigger_event if provided
        trigger_event = getattr(entity, "trigger_event", None)
        if trigger_event:
            event_code = trigger_event
            msg_type = f"ADT^{trigger_event}"
        else:
            # Priority 1.5: Auto-detect A06/A07 based on movement history
            a0607_code, _prev = detect_a06_a07_from_history(entity, session, operation)
            if a0607_code:
                event_code = a0607_code
                msg_type = f"ADT^{a0607_code}"
            else:
                # Priority 2: Use movement_type mapping
                metier_type = getattr(entity, "movement_type", None)
                hl7_code = to_standard_movement_code(metier_type, "hl7")
                
                if hl7_code:
                    msg_type = hl7_code
                    event_code = hl7_code.split("^")[1] if "^" in hl7_code else "A99"
                else:
                    # Priority 3: Use operation to determine event
                    action = getattr(entity, "action", None)
                    if action == "CANCEL":
                        original_trigger = getattr(entity, "original_trigger", None)
                        cancel_events = {
                            "A01": "A11", "A04": "A11", "A03": "A13",
                            "A02": "A12", "A05": "A38", "A15": "A26",
                            "A21": "A52", "A22": "A53", "A54": "A55",
                            "A06": "A07", "A07": "A06",
                        }
                        event_code = cancel_events.get(original_trigger, "A12")
                        msg_type = f"ADT^{event_code}"
                    elif operation == "update":
                        event_code = "Z99"  # Generic/Custom event for modifications
                        msg_type = "ADT^Z99"
                    else:
                        event_code = "A01"  # Admit Patient for new movements (default)
                        msg_type = "ADT^A01"
        
        # Get venue and patient info
        # Explicitly load venue if not already loaded
        if hasattr(entity, 'venue_id') and entity.venue_id and not getattr(entity, 'venue', None):
            venue = session.exec(select(Venue).where(Venue.id == entity.venue_id)).first()
        else:
            venue = entity.venue if hasattr(entity, 'venue') else None
        
        # Load dossier from venue
        if venue and hasattr(venue, 'dossier_id') and venue.dossier_id and not getattr(venue, 'dossier', None):
            dossier = session.exec(select(Dossier).where(Dossier.id == venue.dossier_id)).first()
        else:
            dossier = venue.dossier if venue and hasattr(venue, 'dossier') else None
        
        # Load patient from dossier
        if dossier and hasattr(dossier, 'patient_id') and dossier.patient_id and not getattr(dossier, 'patient', None):
            patient = session.exec(select(Patient).where(Patient.id == dossier.patient_id)).first()
        else:
            patient = dossier.patient if dossier and hasattr(dossier, 'patient') else None
        # Build timestamp
        timestamp = entity.when.strftime("%Y%m%d%H%M%S") if entity.when else ""
        # Build MSH segment avec structure de message et version IHE PAM France
        control_id = _new_message_control_id(entity.mouvement_seq)
        # Determine message structure based on event code (IHE PAM France)
        if event_code in ["A01", "A04", "A05", "A08", "A13", "A28", "A31", "Z99"]:
            msg_structure = "ADT_A01"
        elif event_code == "A02":
            msg_structure = "ADT_A02"
        elif event_code == "A03":
            msg_structure = "ADT_A03"
        elif event_code in ["A06", "A07"]:
            msg_structure = "ADT_A06"
        elif event_code in ["A09", "A10", "A11"]:
            msg_structure = "ADT_A09"
        elif event_code in ["A12", "A15"]:
            msg_structure = "ADT_A12"
        elif event_code in ["A21", "A22", "A52", "A53"]:
            msg_structure = "ADT_A21"
        elif event_code in ["A38", "A40"]:
            msg_structure = "ADT_A38"
        else:
            msg_structure = f"ADT_{event_code}"
        sending_app = msh_sending_app or "POC"
        sending_fac = msh_sending_facility or "HOSP"
        receiving_app = msh_receiving_app or "EXT"
        receiving_fac = msh_receiving_facility or "HOSP"
        if event_code == "Z99":
            msh = rf"MSH|^~\&|{sending_app}|{sending_fac}|{receiving_app}|{receiving_fac}|{timestamp}||ADT^Z99^ADT_A01|{control_id}|P|2.5^FRA^2.11|||||FRA|8859/1"
        else:
            msh = rf"MSH|^~\&|{sending_app}|{sending_fac}|{receiving_app}|{receiving_fac}|{timestamp}||ADT^{event_code}^{msg_structure}|{control_id}|P|2.5^FRA^2.11|||||FRA|8859/1"
        
        # Build EVN segment
        evn = f"EVN|{event_code}|{timestamp}"
        
        # Build PID segment if we have patient info
        if patient:
            assigning_system = forced_identifier_system or "HOSP"
            assigning_oid = forced_identifier_oid
            patient_id = patient.identifier or str(patient.id)
            authority = f"{assigning_system}&{assigning_oid}&ISO" if assigning_oid else assigning_system
            pid3 = f"{patient_id}^^^{authority}^PI"
            family = patient.family or ""
            given = patient.given or ""
            if patient.birth_date:
                if hasattr(patient.birth_date, 'strftime'):
                    birth_date = patient.birth_date.strftime("%Y%m%d")
                else:
                    birth_date = str(patient.birth_date).replace("-", "")
            else:
                birth_date = ""
            gender = patient.gender or ""
            
            # PID-18: Patient Account Number (numéro de dossier pour IHE PAM France)
            # Prefer VN namespace (visit number namespace) for visit/account identifiers; fallback to dossier/id when sequences are missing
            account_number_raw = ""
            if dossier and getattr(dossier, 'dossier_seq', None):
                account_number_raw = str(dossier.dossier_seq)
            elif dossier and getattr(dossier, 'id', None):
                account_number_raw = str(dossier.id)
            elif venue and getattr(venue, 'venue_seq', None):
                account_number_raw = str(venue.venue_seq)
            elif getattr(entity, 'mouvement_seq', None):
                account_number_raw = str(entity.mouvement_seq)

            authority_vn, vn_type = _resolve_namespace_authority(
                session,
                getattr(dossier, 'entite_juridique_id', None),
                "VN",
                forced_system=forced_identifier_system,
                forced_oid=forced_identifier_oid,
            )
            authority_vn = authority_vn or (forced_identifier_system or "HOSP")
            vn_type = vn_type or "VN"
            account_number = f"{account_number_raw}^^^{authority_vn}^{vn_type}" if account_number_raw else ""

            if not account_number:
                fallback_value = str(getattr(entity, 'mouvement_seq', None) or getattr(venue, 'venue_seq', None) or getattr(dossier, 'id', None) or "0")
                fallback_auth, fallback_type = _resolve_namespace_authority(
                    session,
                    getattr(dossier, 'entite_juridique_id', None),
                    "NDA",
                    forced_system=forced_identifier_system,
                    forced_oid=forced_identifier_oid,
                )
                fallback_auth = fallback_auth or (forced_identifier_system or "HOSP")
                fallback_type = fallback_type or "AN"
                account_number = f"{fallback_value}^^^{fallback_auth}^{fallback_type}"
            
            # Build complete PID segment with PID-18 (Patient Account Number) using indexed fields
            name_field = _build_patient_name(
                family,
                given,
                getattr(patient, "middle", None),
                getattr(patient, "suffix", None),
                getattr(patient, "prefix", None),
                getattr(patient, "birth_family", None),
            )
            pid_fields = [""] * 40
            pid_fields[0] = "PID"
            pid_fields[1] = "1"
            pid_fields[3] = pid3
            pid_fields[5] = _c_local(name_field)
            pid_fields[7] = birth_date
            pid_fields[8] = gender

            if patient:
                addr = [
                    patient.address or "",
                    "",
                    patient.city or "",
                    patient.state or "",
                    patient.postal_code or "",
                    patient.country or "",
                    "H",
                ]
                pid_fields[11] = "^".join(addr)
                xtn_parts = []
                if getattr(patient, "phone", None):
                    xtn_parts.append(f"^PRN^PH^^^^{patient.phone}")
                if getattr(patient, "mobile", None):
                    xtn_parts.append(f"^ORN^CP^^^^{patient.mobile}")
                if getattr(patient, "email", None):
                    xtn_parts.append(f"^NET^Internet^{patient.email}")
                if xtn_parts:
                    pid_fields[13] = "~".join(xtn_parts)

            pid_fields[18] = account_number
            if patient:
                pid_fields[32] = _c_local(getattr(patient, "identity_reliability_code", None) or "")
            pid = "|".join(pid_fields)
        else:
            # If only OID is provided without system, Solution de repli to HOSP system
            authority = (
                f"HOSP&{forced_identifier_oid}&ISO" if forced_identifier_oid else "HOSP"
            )
            pid = f"PID|1||UNKNOWN^^^{authority}^PI||UNKNOWN^UNKNOWN||||||||||||||||||||"
        
        # Build PV1 segment avec mapping vocabulaire
        from app.services.vocabulary_translate import map_code
        
        # Déterminer encounter_class depuis le dossier pour mapper vers patient_class
        if dossier:
            dossier_type_val = getattr(dossier, "dossier_type", None)
            if hasattr(dossier_type_val, "value"):
                dossier_type_val = dossier_type_val.value
            encounter_class = str(dossier_type_val) if dossier_type_val else "IMP"
            
            # Utiliser le mapping vocabulaire
            patient_class = map_code(
                session,
                source_system_name="encounter-class",
                source_code=encounter_class,
                target_system_name="patient-class"
            )
            
            # Solution de repli si pas de mapping
            if not patient_class:
                patient_class_map = {"hospitalise": "I", "externe": "O", "urgence": "E", "IMP": "I", "AMB": "O", "EMER": "E"}
                patient_class = patient_class_map.get(encounter_class, "I")
        else:
            patient_class = "I"  # Inpatient by default
        
        location = entity.location or entity.to_location or ""
        if venue:
            uf_resp = venue.uf_responsabilite or ""
        elif dossier:
            uf_resp = dossier.uf_responsabilite or ""
        else:
            uf_resp = ""
        
        # PV1-19 (Visit Number) - use venue_seq (numéro de venue)
        visit_number_pv1 = str(venue.venue_seq) if venue else str(entity.mouvement_seq)
        
        # PV1-19 (Visit Number) - use venue_seq (numéro de venue) as full CX
        # PV1-19 (Visit Number) - use venue_seq (numéro de venue) as full CX
        authority_vn, vn_type = _resolve_namespace_authority(
            session, getattr(dossier, 'entite_juridique_id', None) if dossier else getattr(venue, 'entite_juridique_id', None),
            "VN",
            forced_system=forced_identifier_system, forced_oid=forced_identifier_oid
        )
        pv1_19 = f"{visit_number_pv1}^^^{authority_vn}^{vn_type}"
        # Indexed construction prevents an off-by-one field shift. PV1-19 is
        # the venue identifier, PV1-44 the admission timestamp and PV1-52 the
        # responsible UF; those positions are read by the inbound PAM parser.
        pv1_fields = [""] * 53
        pv1_fields[0] = "PV1"
        pv1_fields[1] = "1"
        pv1_fields[2] = patient_class
        pv1_fields[3] = location
        pv1_fields[19] = pv1_19
        if dossier and getattr(dossier, "admit_time", None):
            pv1_fields[44] = dossier.admit_time.strftime("%Y%m%d%H%M%S")
        else:
            pv1_fields[44] = timestamp
        pv1_fields[52] = uf_resp
        pv1 = "|".join(pv1_fields)

        # ZBE segment generation for mouvement (same format as venue)
        # ZBE-1 is repeatable (EI~EI~...) for cooperative Movement Management : several
        # systems can each carry their own identifier for the same physical movement.
        # Our own internal identifier (mouvement_seq) always leads the repetition list —
        # it's what lets us resolve a future Z99 correction via a direct mouvement_seq
        # match when the correspondent simply echoes back the first ZBE-1 repetition —
        # followed by any external MVT identifiers we've recorded for this movement
        # (e.g. one this Mouvement was originally created from, on the receive side).
        zbe_id = control_id
        try:
            mvt_auth, mvt_type = _resolve_namespace_authority(
                session, getattr(dossier, 'entite_juridique_id', None), "MVT",
                forced_system=forced_identifier_system, forced_oid=forced_identifier_oid
            )
            if mvt_auth:
                own_authority = mvt_auth
            elif forced_identifier_system and forced_identifier_oid:
                own_authority = f"{forced_identifier_system}&{forced_identifier_oid}&ISO"
            else:
                own_authority = forced_identifier_system or "HOSP"
            own_type = mvt_type or "MVT"
            zbe_id_reps = [f"{entity.mouvement_seq}^^^{own_authority}^{own_type}"]

            mv_idents = []
            if session:
                mv_idents = session.exec(
                    select(Identifier)
                    .where(Identifier.mouvement_id == entity.id)
                    .where(Identifier.type == IdentifierType.MVT)
                    .where(Identifier.status == "active")
                ).all()
            for mv_ident in mv_idents:
                # Prefer namespace lookup by entite_juridique and type MVT
                ns_auth, ns_type = _resolve_namespace_authority(
                    session, getattr(dossier, 'entite_juridique_id', None), "MVT",
                    forced_system=mv_ident.system, forced_oid=mv_ident.oid
                )
                # Build assigning authority in the form 'system&oid&ISO' when possible
                if ns_auth:
                    authority = ns_auth
                else:
                    if getattr(mv_ident, 'system', None) and getattr(mv_ident, 'oid', None):
                        authority = f"{mv_ident.system}&{mv_ident.oid}&ISO"
                    elif getattr(mv_ident, 'system', None):
                        authority = mv_ident.system
                    elif getattr(mv_ident, 'oid', None):
                        authority = f"HOSP&{mv_ident.oid}&ISO"
                    else:
                        authority = "HOSP"
                type_code = ns_type or "MVT"
                # ZBE-1 movement identifier as CX: value^^^assigningAuthority^type
                zbe_id_reps.append(f"{mv_ident.value}^^^{authority}^{type_code}")

            zbe_id = "~".join(zbe_id_reps)
        except Exception:
            # Keep control_id as Solution de repli on any error
            zbe_id = control_id
        
        # ZBE-4: Action (INSERT, UPDATE, CANCEL)
        action = getattr(entity, "action", None) or "INSERT"
        if not action:
            # Determine action based on event code if not explicitly set
            action = "UPDATE" if event_code in ["A08", "A31"] else "TRANSFER" if event_code == "A02" else "DISCHARGE" if event_code == "A03" else "INSERT"
        
        historic = "N"
        
        # ZBE-6: Original trigger (for CANCEL actions)
        original_trigger = getattr(entity, "original_trigger", None) or ""
        
        # ZBE-7: UF médicale = UF de responsabilité (XON format: label^code^code_type^^^id^^^id_type^assigning_authority^component10=code)
        uf_responsabilite = getattr(entity, "uf_responsabilite", None) or getattr(venue, "uf_responsabilite", None) or getattr(dossier, "uf_responsabilite", None) or ""
        # XON format: name (1) ^ code (2) ^ type (3) ^ ... ^ code (10)
        # We need at least component 10 filled with the code
        if uf_responsabilite:
            zbe_7_comps = [""] * 10
            zbe_7_comps[0] = uf_responsabilite  # Component 1: label/code
            zbe_7_comps[9] = uf_responsabilite  # Component 10: code
            zbe_7 = "^".join(zbe_7_comps)
        else:
            zbe_7 = ""
        
        # ZBE-8: UF de soins (XON format - same as ZBE-7)
        uf_soins_code = getattr(entity, "uf_soins_code", None) or getattr(venue, "uf_soins_code", None) or getattr(dossier, "uf_soins_code", None) or ""
        uf_soins_label = getattr(entity, "uf_soins_label", None) or getattr(venue, "uf_soins_label", None) or getattr(dossier, "uf_soins_label", None) or ""
        if uf_soins_code:
            zbe_8_comps = [""] * 10
            zbe_8_comps[0] = uf_soins_label  # Component 1: label
            zbe_8_comps[9] = uf_soins_code  # Component 10: code
            zbe_8 = "^".join(zbe_8_comps)
        else:
            zbe_8 = ""
        
        # ZBE-9: nature du mouvement (S,H,M,L,D,SM)
        from app.services.nature_mapping import derive_nature
        nature = getattr(entity, "nature", None)
        zbe_9 = derive_nature(event_code, nature)
        valid_natures = {"S", "H", "M", "L", "D", "SM", "SH", "MH", "LD", "HMS", "C"}
        if not zbe_9 or zbe_9 not in valid_natures:
            zbe_9 = "H"  # Default to hospitalisation
        
        # Build ZBE segment respecting official field order. ZBE-3 carries the movement code used
        # by validators, while ZBE-4 still exposes the action indicator expected by downstream feeds.
        movement_code = getattr(entity, "movement_code", None)
        if not movement_code:
            # Map common HL7 events to textual movement codes when no explicit code is provided.
            event_to_movement = {
                "A01": "ADMIT",
                "A02": "TRANSFER",
                "A03": "DISCHARGE",
                "A06": "ADMIT",
                "A07": "TRANSFER",
                "A11": "TRANSFER",
                "A12": "DELETE",
                "A13": "DELETE",
                "A31": "UPDATE",
                "Z99": "UPDATE",
            }
            movement_code = event_to_movement.get(event_code, action or "INSERT")
        zbe_fields = [
            "ZBE",
            zbe_id,
            timestamp,
            movement_code,
            action or movement_code,
            historic,
        ]
        if (action in ["CANCEL", "UPDATE"]) and original_trigger:
            zbe_fields.append(original_trigger)
        else:
            zbe_fields.append("")
        zbe_fields.extend([zbe_7, zbe_8, zbe_9])
        zbe = "|".join(zbe_fields)
        
        # Combine all segments with \r separator (HL7 standard)
        return normalize_generated_message("\r".join([msh, evn, pid, pv1, zbe]))
    
    return ""


def emit_to_senders_async(
    entity,
    entity_type: Literal["patient", "dossier", "venue", "mouvement", "ccam_act", "ngap_act", "ucd_act", "lpp_act"],
    session: Session,
    operation: str = "insert",
    mrg_prior_identifiers: Optional[list] = None,
    mrg_prior_name: str | None = None,
) -> None:
    """Emit HL7/FHIR/HPRIM notifications for newly created or updated entities and acts."""

    endpoints = list_eligible_sender_endpoints(session, entity)
    base_correlation_id = getattr(entity, "correlation_id", None)

    for endpoint in endpoints:
        correlation_id = base_correlation_id
        # create a snapshot once per endpoint loop if needed
        use_snapshot = True
        try:
            # allow endpoints to opt-out in future via attribute, keep default True
            use_snapshot = getattr(endpoint, 'use_snapshot_emission', True)
        except Exception:
            use_snapshot = True
        snapshot = None
        if use_snapshot:
            snapshot = _snapshot_entity(entity, entity_type, session)
        
        # ================================================================================
        # FILTRAGE PAR TYPE D'ENTITÉ ET ABONNEMENT
        # Chaque bloc vérifie : 1) le type d'endpoint, 2) l'abonnement activé, 
        # 3) le type d'entité compatible, 4) la configuration requise
        # ================================================================================
        
        # HL7 IHE PAM (identité/mouvements) - MLLP uniquement
        # Types d'entités compatibles : patient, venue, mouvement
        if endpoint.kind == "MLLP" and entity_type in ["patient", "venue", "mouvement"]:
            # Vérifier si l'abonnement HL7 PAM est activé
            if not getattr(endpoint, "emit_hl7_pam", True):
                logger.debug(f"[MLLP] Endpoint {endpoint.id} has emit_hl7_pam=False - skipping PAM emission for {entity_type}")
                # Ne pas utiliser continue ici, on veut permettre d'autres types d'émission
            # Vérifier que l'endpoint MLLP est bien configuré
            elif not endpoint.host or not endpoint.port:
                logger.debug(f"[MLLP] Endpoint {endpoint.id} not properly configured (missing host/port) - skipping PAM emission")
            else:
                # Prefer using the live model instance for generation when available
                gen_entity = entity if not isinstance(entity, dict) else (snapshot if snapshot is not None else entity)
                hl7_message = generate_pam_hl7(
                    gen_entity,
                    entity_type,
                    session,
                    forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
                    forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
                    operation=operation,
                    msh_sending_app=getattr(endpoint, 'sending_app', None),
                    msh_sending_facility=getattr(endpoint, 'sending_facility', None),
                    msh_receiving_app=getattr(endpoint, 'receiving_app', None),
                    msh_receiving_facility=getattr(endpoint, 'receiving_facility', None),
                    mrg_prior_identifiers=mrg_prior_identifiers,
                    mrg_prior_name=mrg_prior_name,
                )
                if hl7_message is None or (isinstance(hl7_message, str) and hl7_message.strip() == ""):
                    hl7_message = "[Emission error: HL7 message not generated]"
                try:
                    # Import tardif : le parseur reste remplaçable par les tests.
                    from app.services.mllp import parse_msh_fields
                    hl7_fields = parse_msh_fields(hl7_message)
                    control_id = hl7_fields.get("control_id")
                except Exception:
                    control_id = None
                correlation_id = control_id or correlation_id
                # Une seule tentative ici : les reprises réseau relèvent de
                # l'outbox persistante et de son backoff.
                emit_outbound_pam_attempt(
                    session,
                    endpoint=endpoint,
                    payload=hl7_message,
                    correlation_id=correlation_id,
                    entity_id=getattr(entity, "id", "unknown"),
                    message_type=hl7_fields.get("msg_type") or "ADT^unknown",
                )
        # HL7 MFN (structure) - MLLP uniquement
        # Types d'entités compatibles : structure
        if endpoint.kind == "MLLP" and entity_type == "structure":
            if not getattr(endpoint, "emit_hl7_mfn", True):
                logger.debug(f"[MLLP] Endpoint {endpoint.id} has emit_hl7_mfn=False - skipping MFN emission")
            elif not endpoint.host or not endpoint.port:
                logger.debug(f"[MLLP] Endpoint {endpoint.id} not properly configured (missing host/port) - skipping MFN emission")
            else:
                # MFN emission logic here (call your MFN generator and sender)
                pass
        
        # FHIR structure (Location/Organization) - FHIR uniquement
        # Types d'entités compatibles : dossier, venue
        if endpoint.kind == "FHIR" and entity_type in ["dossier", "venue"]:
            if not getattr(endpoint, "emit_fhir_structure", True):
                logger.debug(f"[FHIR] Endpoint {endpoint.id} has emit_fhir_structure=False - skipping structure emission for {entity_type}")
            elif not endpoint.base_url:
                logger.debug(f"[FHIR] Endpoint {endpoint.id} not properly configured (missing base_url) - skipping structure emission")
            else:
                # Prefer using the live model instance for generation when available
                gen_entity = entity if not isinstance(entity, dict) else (snapshot if snapshot is not None else entity)
                fhir_payload = generate_fhir(
                    gen_entity,
                    entity_type,
                    session,
                    forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
                    forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
                )
                emit_fhir_payload(
                    session,
                    endpoint=endpoint,
                    payload=fhir_payload,
                    correlation_id=correlation_id,
                )
        
        # FHIR identity/movements (Patient/Encounter) - FHIR uniquement
        # Types d'entités compatibles : patient, mouvement, venue
        if endpoint.kind == "FHIR" and entity_type in ["patient", "mouvement", "venue"]:
            if not getattr(endpoint, "emit_fhir_identity", True):
                logger.debug(f"[FHIR] Endpoint {endpoint.id} has emit_fhir_identity=False - skipping identity emission for {entity_type}")
            elif not endpoint.base_url:
                logger.debug(f"[FHIR] Endpoint {endpoint.id} not properly configured (missing base_url) - skipping identity emission")
            else:
                # Prefer using the live model instance for generation when available
                gen_entity = entity if not isinstance(entity, dict) else (snapshot if snapshot is not None else entity)
                fhir_payload = generate_fhir(
                    gen_entity,
                    entity_type,
                    session,
                    forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
                    forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
                )
                emit_fhir_payload(
                    session,
                    endpoint=endpoint,
                    payload=fhir_payload,
                    correlation_id=correlation_id,
                )

        # HPRIM endpoints: emit HPRIM XML messages for cotation (AUTO-TRANSMISSION)
        # HPRIM is used specifically for medical billing/cotation (CCAM, NGAP, UCD, LPP)
        # Auto-transmission enabled for cotation acts (like PAM/FHIR for entities)
        # Types d'entités compatibles : ccam_act, ngap_act, ucd_act, lpp_act
        if endpoint.kind == "HPRIM" and entity_type in ["ccam_act", "ngap_act", "ucd_act", "lpp_act"]:
            try:
                emit_hprim_act(
                    session,
                    entity=entity,
                    entity_type=entity_type,
                    endpoint=endpoint,
                    operation=operation,
                    correlation_id=correlation_id,
                )
            except Exception:
                logger.exception("[HPRIM] Error generating message for %s %s", entity_type, entity.id)
                continue
        
        # SFTP outbox: write HL7/FHIR payloads to a remote SFTP if configured
        if endpoint.kind == "SFTP":
            from datetime import datetime
            import os
            import random
            try:
                from app.adapters.sftp_writer import SFTPWriter
                # Build HL7 for PAM events (patient/venue/mouvement)
                hl7_message = None
                if entity_type in ["patient", "venue", "mouvement"]:
                    hl7_message = generate_pam_hl7(
                        entity,
                        entity_type,
                        session,
                        operation=operation,
                        msh_sending_app=getattr(endpoint, 'sending_app', None),
                        msh_sending_facility=getattr(endpoint, 'sending_facility', None),
                        msh_receiving_app=getattr(endpoint, 'receiving_app', None),
                        msh_receiving_facility=getattr(endpoint, 'receiving_facility', None),
                    )
                # Fallback to FHIR payload when HL7 not applicable
                if not hl7_message:
                    fhir_payload = generate_fhir(entity, entity_type, session)
                    payload_str = json.dumps(fhir_payload, default=str)
                    ext = "json"
                else:
                    payload_str = hl7_message
                    ext = "hl7"

                # Unique filename: entityType_id_timestamp-rand.ext
                suffix = f"{int(datetime.utcnow().timestamp())}-{random.randint(1000,9999)}"
                filename = f"{entity_type}_{getattr(entity,'id', 'unknown')}_{suffix}.{ext}"
                remote_path = endpoint.ftp_remote_outbox_path or "."
                writer = SFTPWriter(
                    host=endpoint.ftp_host,
                    port=endpoint.ftp_port or 22,
                    username=endpoint.ftp_username,
                    password=endpoint.ftp_password,
                    remote_path=remote_path
                )
                writer.connect()
                writer.write_file(filename, payload_str)
                writer.disconnect()
                # Record MessageLog
                endpoint_id = endpoint.id
                log = MessageLog(
                    direction="out",
                    kind="SFTP",
                    endpoint_id=endpoint_id,
                    payload=(payload_str[:100000] if payload_str else ""),
                    ack_payload=f"SENT_SFTP:{filename}",
                    status="sent",
                    correlation_id=getattr(entity, 'correlation_id', None),
                )
                session.add(log)
                session.commit()
            except Exception as exc:
                endpoint_id_safe = locals().get('endpoint_id', getattr(endpoint, 'id', 'unknown'))
                logger.error(f"[emit_on_create] Failed to write SFTP outbox for endpoint={endpoint_id_safe}: {exc}")
                session.rollback()
                try:
                    log = MessageLog(
                        direction="out",
                        kind="SFTP",
                        endpoint_id=endpoint_id_safe if isinstance(endpoint_id_safe, int) else None,
                        payload=(payload_str[:100000] if 'payload_str' in locals() and payload_str else ""),
                        ack_payload=str(exc),
                        status="error",
                        correlation_id=getattr(entity, 'correlation_id', None),
                    )
                    session.add(log)
                    session.commit()
                except Exception:
                    logger.exception("Failed to persist SFTP MessageLog after write failure")

        # FILE outbox: write HL7/FHIR payloads to a filesystem outbox if configured
        if endpoint.kind == "FILE":
            # Write HL7 / FHIR payloads to filesystem outbox. If the endpoint has an
            # explicit outbox_path configured, use it; otherwise fall back to
            # MEDBRIDGE_OUT_DIR env or /tmp/medbridge_generated to make test runs
            # reliably produce inspectable files.
            from datetime import datetime
            import os
            import random
            try:
                # Build HL7 for PAM events (patient/venue/mouvement)
                hl7_message = None
                if entity_type in ["patient", "venue", "mouvement"]:
                    hl7_message = generate_pam_hl7(
                        entity,
                        entity_type,
                        session,
                        operation=operation,
                        msh_sending_app=getattr(endpoint, 'sending_app', None),
                        msh_sending_facility=getattr(endpoint, 'sending_facility', None),
                        msh_receiving_app=getattr(endpoint, 'receiving_app', None),
                        msh_receiving_facility=getattr(endpoint, 'receiving_facility', None),
                    )
                # Fallback to FHIR payload when HL7 not applicable
                if not hl7_message:
                    fhir_payload = generate_fhir(entity, entity_type, session)
                    payload_str = json.dumps(fhir_payload, default=str)
                    ext = "json"
                else:
                    payload_str = hl7_message
                    ext = "hl7"

                # Determine base outbox: endpoint.outbox_path > MEDBRIDGE_OUT_DIR env > /tmp/medbridge_generated
                base_outbox = (getattr(endpoint, 'outbox_path', None)) or os.environ.get('MEDBRIDGE_OUT_DIR') or "/tmp/medbridge_generated"
                # Choose a sensible subdirectory per payload type
                if ext == "hl7":
                    sub = "pam"
                elif ext == "json":
                    sub = "fhir"
                else:
                    sub = entity_type

                outbox = os.path.join(base_outbox, sub)
                os.makedirs(outbox, exist_ok=True)

                # Unique filename: entityType_id_timestamp-rand.ext
                suffix = f"{int(datetime.utcnow().timestamp())}-{random.randint(1000,9999)}"
                filename = f"{entity_type}_{getattr(entity,'id', 'unknown')}_{suffix}.{ext}"
                filepath = os.path.join(outbox, filename)

                # Atomic write: write to tmp then replace
                tmp_path = filepath + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(payload_str)
                os.replace(tmp_path, filepath)

                # Record MessageLog (truncate payload to reasonable size)
                # Capture endpoint.id AVANT commit pour éviter accès après détachement
                endpoint_id = endpoint.id
                log = MessageLog(
                    direction="out",
                    kind="FILE",
                    endpoint_id=endpoint_id,
                    payload=(payload_str[:100000] if payload_str else ""),
                    ack_payload=f"WROTE:{filepath}",
                    status="sent",
                    correlation_id=getattr(entity, 'correlation_id', None),
                )
                session.add(log)
                session.commit()
            except Exception as exc:
                # Utiliser endpoint_id capturé au lieu de endpoint.id (objet peut être détaché)
                endpoint_id_safe = locals().get('endpoint_id', getattr(endpoint, 'id', 'unknown'))
                logger.error(f"[emit_on_create] Failed to write FILE outbox for endpoint={endpoint_id_safe}: {exc}")
                session.rollback()  # Rollback explicite pour réinitialiser la session
                try:
                    log = MessageLog(
                        direction="out",
                        kind="FILE",
                        endpoint_id=endpoint_id_safe if isinstance(endpoint_id_safe, int) else None,
                        payload=(payload_str[:100000] if 'payload_str' in locals() and payload_str else ""),
                        ack_payload=str(exc),
                        status="error",
                        correlation_id=getattr(entity, 'correlation_id', None),
                    )
                    session.add(log)
                    session.commit()
                except Exception:
                    logger.exception("Failed to persist FILE MessageLog after write failure")

    if not endpoints:
        # No sender configured: store generated payloads for audit trail.
        hl7_message = generate_pam_hl7(entity, entity_type, session)
        validation = validate_outbound_pam(hl7_message)
        pam_status = validation.status
        pam_issues = validation.issues
        fhir_payload = generate_fhir(entity, entity_type, session)
        log1 = MessageLog(
            direction="out",
            kind="MLLP",
            endpoint_id=None,
            payload=hl7_message or "",
            ack_payload="",
            status="generated",
            pam_validation_status=pam_status,
            pam_validation_issues=pam_issues,
        )
        log2 = MessageLog(
            direction="out",
            kind="FHIR",
            endpoint_id=None,
            payload=json.dumps(fhir_payload, default=str) if fhir_payload is not None else "",
            ack_payload="",
            status="generated",
        )
        session.add(log1)
        session.add(log2)
        session.commit()
        # Also write generated payloads to /tmp for easier inspection when no senders are configured.
        try:
            import os
            import random
            base = os.environ.get('MEDBRIDGE_OUT_DIR') or '/tmp/medbridge_generated'
            hl7_out = os.path.join(base, 'pam')
            fhir_out = os.path.join(base, 'fhir')
            os.makedirs(hl7_out, exist_ok=True)
            os.makedirs(fhir_out, exist_ok=True)
            # HL7 file
            try:
                if hl7_message:
                    from app.utils.atomic_write import write_atomic_text
                    basename = f"{entity_type}_{getattr(entity,'id','unknown')}"
                    write_atomic_text(Path(hl7_out), basename, hl7_message, extension='.hl7')
            except Exception:
                logger.exception('Failed to write fallback HL7 file to /tmp')
            # FHIR file
            try:
                if fhir_payload is not None:
                    from app.utils.atomic_write import write_atomic_text
                    basename = f"fhir_{entity_type}_{getattr(entity,'id','unknown')}"
                    write_atomic_text(Path(fhir_out), basename, json.dumps(fhir_payload, default=str, ensure_ascii=False), extension='.json')
            except Exception:
                logger.exception('Failed to write fallback FHIR file to /tmp')
        except Exception:
            logger.exception('Failed to persist fallback files to /tmp')


class _EmitToSendersWrapper:
    """Allow emit_to_senders to be used in sync and async contexts."""

    def __init__(self, async_callable):
        self._async = async_callable

    def __call__(self, entity, entity_type, session: Session, **kwargs):
        # The underlying implementation may be async (returning a coroutine)
        # or synchronous (returning None or a regular value). Detect and
        # handle both cases to avoid passing None to asyncio.run.
        result = self._async(entity, entity_type, session, **kwargs)
        # If the underlying call returned a coroutine, either run it
        # synchronously when no loop is running, or return it for the
        # caller to await when a loop is present.
        if asyncio.iscoroutine(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # No running loop: run synchronously
                return asyncio.run(result)
            else:
                # Running loop present: return coroutine to be awaited by caller
                return result
        # Not a coroutine: it's a regular/sync function result (possibly None)
        return result


emit_to_senders = _EmitToSendersWrapper(emit_to_senders_async)

__all__ = ["emit_to_senders", "emit_to_senders_async"]
