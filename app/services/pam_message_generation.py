"""Génération des messages IHE PAM à partir des entités métier."""

import logging
from typing import Literal, Optional

from sqlmodel import Session, select

from app.models import Dossier
from app.models_identifiers import Identifier, IdentifierType
from app.services.hl7_fields import build_adt_header, build_patient_name, build_xad, to_hl7_administrative_sex
from app.services.pam_profile_fr import format_xtn, normalize_generated_message
from app.services.pam_identifiers import build_pid3_identifiers
from app.services.pam_emission_primitives import (
    clean_hl7_value as _c,
    new_message_control_id as _new_message_control_id,
    normalize_mrg_prior_identifiers as _normalize_mrg_prior_identifiers,
)
from app.services.pam_namespace import resolve_namespace_authority as _resolve_namespace_authority
from app.services.pam_movement_events import message_structure_for_event, select_movement_event
from app.services.pam_movement_context import load_movement_context
from app.services.pam_movement_segments import build_movement_pv1
from app.services.zbe_fields import build_xon_unit, derive_zbe_nature, movement_action_and_code

logger = logging.getLogger(__name__)


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
        msh, evn = build_adt_header(
            timestamp, event_type, msg_structure, control_id,
            sending_app, sending_fac, receiving_app, receiving_fac,
        )

        # PID-3 identifiers
        pid3 = build_pid3_identifiers(entity, session, forced_system=forced_identifier_system, forced_oid=forced_identifier_oid)


        family = _c_local(_get("family", ""))
        given = _c_local(_get("given", ""))
        middle = _c_local(_get("middle", None))
        suffix = _c_local(_get("suffix", None)) or None
        prefix = _c_local(_get("prefix", None)) or None
        birth_family = _c_local(_get("birth_family", None)) or None
        name = build_patient_name(
            family, given, middle, suffix, prefix, birth_family
        )

        # Birth date
        birth_date_raw = _c_local(_get("birth_date", ""))
        birth_date = birth_date_raw.replace("-", "").replace("/", "")[:8] if birth_date_raw else ""

        # Gender mapping — PID-8 (Sexe) : l'extension nationale IHE FR restreint les valeurs
        # permises à F/M/U (table HL7 0001), pas de code "O" ; "other" est donc mappé sur "U".
        raw_gender = _c_local(_get("gender", ""))
        gender = to_hl7_administrative_sex(raw_gender)

        addresses = []
        street = _c_local(_get("address", None))
        city = _c_local(_get("city", None))
        state = _c_local(_get("state", None))
        postal = _c_local(_get("postal_code", None))
        country = _c_local(_get("country", None))
        # Only add home address repetition if at least one meaningful field exists
        if any([street, city, state, postal, country]):
            addresses.append(build_xad(street, "", city, state, postal, country, "H"))

        birth_street = _c_local(_get("birth_address", None))
        birth_city = _c_local(_get("birth_city", None))
        birth_state = _c_local(_get("birth_state", None))
        birth_postal = _c_local(_get("birth_postal_code", None))
        birth_country = _c_local(_get("birth_country", None))
        if any([birth_street, birth_city, birth_state, birth_postal, birth_country]):
            addresses.append(build_xad(birth_street, "", birth_city, birth_state, birth_postal, birth_country, "BIR"))

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
            gender = to_hl7_administrative_sex(raw_gender)
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

        msh, evn = build_adt_header(admit_time, event_type, msg_structure, control_id)

        # PID-5 keeps the current and birth names in separate XPN repetitions.
        name_field = build_patient_name(
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
        zbe_7 = build_xon_unit(uf_responsabilite)
        # ZBE-8: UF de soins (XON format - same as ZBE-7)
        uf_soins_code = getattr(entity, "uf_soins_code", None) or getattr(dossier, "uf_soins_code", None) or ""
        uf_soins_label = getattr(entity, "uf_soins_label", None) or getattr(dossier, "uf_soins_label", None) or ""
        zbe_8 = build_xon_unit(uf_soins_code, uf_soins_label)
        # ZBE-9: nature du mouvement (S,H,M,L,D,SM)
        nature = getattr(entity, "nature", None)
        zbe_9 = derive_zbe_nature(event_type, nature)
        # ZBE for A05 (venue creation): no ZBE-6 for INSERT
        zbe = f"ZBE|{zbe_id}|{admit_time}||{action}|{historic}||{zbe_7}|{zbe_8}|{zbe_9}"

        return normalize_generated_message("\r".join([msh, evn, pid, pv1, zbe]))
    if entity_type == "mouvement":
        event_code = select_movement_event(session, entity, operation)
        
        venue, dossier, patient = load_movement_context(session, entity)
        # Build timestamp
        timestamp = entity.when.strftime("%Y%m%d%H%M%S") if entity.when else ""
        # Build MSH segment avec structure de message et version IHE PAM France
        control_id = _new_message_control_id(entity.mouvement_seq)
        msg_structure = message_structure_for_event(event_code)
        sending_app = msh_sending_app or "POC"
        sending_fac = msh_sending_facility or "HOSP"
        receiving_app = msh_receiving_app or "EXT"
        receiving_fac = msh_receiving_facility or "HOSP"
        if event_code == "Z99":
            msh, _ = build_adt_header(
                timestamp, "Z99", "ADT_A01", control_id,
                sending_app, sending_fac, receiving_app, receiving_fac,
            )
        else:
            msh, _ = build_adt_header(
                timestamp, event_code, msg_structure, control_id,
                sending_app, sending_fac, receiving_app, receiving_fac,
            )
        
        # Build EVN segment
        _, evn = build_adt_header(timestamp, event_code, msg_structure, control_id)
        
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
            name_field = build_patient_name(
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
        
        pv1 = build_movement_pv1(
            session, entity, venue, dossier, timestamp, _resolve_namespace_authority,
            forced_identifier_system, forced_identifier_oid,
        )

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
        action, movement_code = movement_action_and_code(entity, event_code)
        
        historic = "N"
        
        # ZBE-6: Original trigger (for CANCEL actions)
        original_trigger = getattr(entity, "original_trigger", None) or ""
        
        # ZBE-7: UF médicale = UF de responsabilité (XON format: label^code^code_type^^^id^^^id_type^assigning_authority^component10=code)
        uf_responsabilite = getattr(entity, "uf_responsabilite", None) or getattr(venue, "uf_responsabilite", None) or getattr(dossier, "uf_responsabilite", None) or ""
        zbe_7 = build_xon_unit(uf_responsabilite)
        
        # ZBE-8: UF de soins (XON format - same as ZBE-7)
        uf_soins_code = getattr(entity, "uf_soins_code", None) or getattr(venue, "uf_soins_code", None) or getattr(dossier, "uf_soins_code", None) or ""
        uf_soins_label = getattr(entity, "uf_soins_label", None) or getattr(venue, "uf_soins_label", None) or getattr(dossier, "uf_soins_label", None) or ""
        zbe_8 = build_xon_unit(uf_soins_code, uf_soins_label)
        
        # ZBE-9: nature du mouvement (S,H,M,L,D,SM)
        nature = getattr(entity, "nature", None)
        zbe_9 = derive_zbe_nature(event_code, nature)
        
        # Build ZBE segment respecting official field order. ZBE-3 carries the movement code used
        # by validators, while ZBE-4 still exposes the action indicator expected by downstream feeds.
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


__all__ = ["generate_pam_hl7"]
