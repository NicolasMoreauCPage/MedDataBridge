"""Construction des messages PAM centrés patient.

Ce module isole le rendu PID/PV1/MRG du point d'entrée de génération afin que
les évolutions d'identité ne se mélangent pas aux événements de venue ou de
mouvement.
"""

from datetime import datetime
import logging
from typing import Any

from sqlmodel import Session, select

from app.models import Dossier
from app.services.hl7_fields import (
    build_adt_header,
    build_patient_name,
    build_xad,
    to_hl7_administrative_sex,
)
from app.services.pam_emission_primitives import (
    clean_hl7_value,
    new_message_control_id,
    normalize_mrg_prior_identifiers,
)
from app.services.pam_identifiers import build_pid3_identifiers
from app.services.pam_namespace import resolve_namespace_authority
from app.services.pam_profile_fr import format_xtn, normalize_generated_message


logger = logging.getLogger(__name__)


def generate_patient_message(
    entity: Any,
    session: Session,
    *,
    forced_identifier_system: str | None = None,
    forced_identifier_oid: str | None = None,
    operation: str = "insert",
    msh_sending_app: str | None = None,
    msh_sending_facility: str | None = None,
    msh_receiving_app: str | None = None,
    msh_receiving_facility: str | None = None,
    mrg_prior_identifiers: list | None = None,
    mrg_prior_name: str | None = None,
) -> str:
    """Construit le message PAM d'identité, y compris A40/A47 et MRG."""
    is_dict = isinstance(entity, dict)

    def get_value(attribute: str, default: Any = None) -> Any:
        return entity.get(attribute, default) if is_dict else getattr(entity, attribute, default)

    if operation == "merge":
        event_type = "A40"
    elif operation == "change_id":
        event_type = "A47"
    else:
        event_type = "A31" if operation == "update" else "A28"

    normalized_prior_identifiers = normalize_mrg_prior_identifiers(mrg_prior_identifiers)
    if event_type in {"A40", "A47"} and not normalized_prior_identifiers:
        raise ValueError(f"ADT^{event_type} requiert au moins un identifiant antérieur dans MRG-1")
    if event_type == "A40" and mrg_prior_name and any(
        character in str(mrg_prior_name) for character in "|\r\n"
    ):
        raise ValueError("MRG-7 ne doit pas contenir de séparateur de segment ou de champ")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    control_id = new_message_control_id(get_value("patient_seq", get_value("id", "UNKNOWN")))
    message_structure = {"A40": "ADT_A39", "A47": "ADT_A30"}.get(event_type, "ADT_A05")
    msh, evn = build_adt_header(
        timestamp,
        event_type,
        message_structure,
        control_id,
        msh_sending_app or "POC",
        msh_sending_facility or "HOSP",
        msh_receiving_app or "EXT",
        msh_receiving_facility or "HOSP",
    )

    pid3 = build_pid3_identifiers(
        entity,
        session,
        forced_system=forced_identifier_system,
        forced_oid=forced_identifier_oid,
    )
    family = clean_hl7_value(get_value("family", ""))
    given = clean_hl7_value(get_value("given", ""))
    name = build_patient_name(
        family,
        given,
        clean_hl7_value(get_value("middle", None)),
        clean_hl7_value(get_value("suffix", None)) or None,
        clean_hl7_value(get_value("prefix", None)) or None,
        clean_hl7_value(get_value("birth_family", None)) or None,
    )
    birth_date_raw = clean_hl7_value(get_value("birth_date", ""))
    birth_date = birth_date_raw.replace("-", "").replace("/", "")[:8] if birth_date_raw else ""
    gender = to_hl7_administrative_sex(clean_hl7_value(get_value("gender", "")))

    addresses = []
    home_address = [
        clean_hl7_value(get_value(attribute, None))
        for attribute in ("address", "city", "state", "postal_code", "country")
    ]
    if any(home_address):
        addresses.append(build_xad(home_address[0], "", *home_address[1:], "H"))
    birth_address = [
        clean_hl7_value(get_value(attribute, None))
        for attribute in ("birth_address", "birth_city", "birth_state", "birth_postal_code", "birth_country")
    ]
    if any(birth_address):
        addresses.append(build_xad(birth_address[0], "", *birth_address[1:], "BIR"))
    patient_address = "~".join(addresses)

    phones = []
    for attribute, use, equipment in (
        ("phone", "PRN", "PH"),
        ("mobile", "ORN", "CP"),
        ("work_phone", "WPN", "PH"),
    ):
        number = clean_hl7_value(get_value(attribute, ""))
        if number:
            phones.append(format_xtn(number=number, use=use, equipment=equipment))
    email = clean_hl7_value(get_value("email", ""))
    if email:
        phones.append(format_xtn(use="NET", equipment="Internet", email=email))

    account_number = _patient_account_number(
        get_value,
        session,
        forced_identifier_system,
        forced_identifier_oid,
    )
    pid_fields = [""] * 33
    pid_fields[0] = "PID"
    pid_fields[1] = "1"
    pid_fields[3] = clean_hl7_value(pid3)
    pid_fields[5] = clean_hl7_value(name)
    pid_fields[7] = birth_date
    pid_fields[8] = gender
    pid_fields[11] = clean_hl7_value(patient_address)
    pid_fields[13] = "~".join(phones)
    pid_fields[16] = clean_hl7_value(get_value("marital_status", ""))
    pid_fields[18] = clean_hl7_value(account_number)
    pid_fields[23] = clean_hl7_value(get_value("birth_city", ""))
    pid_fields[32] = clean_hl7_value(get_value("identity_reliability_code", ""))
    pid = "|".join(pid_fields)

    if event_type in {"A40", "A47"}:
        mrg_fields = [""] * 8
        mrg_fields[0] = "MRG"
        mrg_fields[1] = "~".join(clean_hl7_value(value) for value in normalized_prior_identifiers)
        if mrg_prior_name:
            mrg_fields[7] = clean_hl7_value(mrg_prior_name)
        return normalize_generated_message("\r".join([msh, evn, pid, "|".join(mrg_fields)]))

    visit_number = clean_hl7_value(str(get_value("patient_seq") or get_value("id") or "0"))
    authority, identifier_type = resolve_namespace_authority(
        session,
        get_value("entite_juridique_id"),
        "VN",
        forced_identifier_system,
        forced_identifier_oid,
    )
    pv1_fields = [""] * 40
    pv1_fields[0], pv1_fields[1], pv1_fields[2] = "PV1", "1", "O"
    pv1_fields[19] = f"{visit_number}^^^{authority or clean_hl7_value('HOSP')}^{identifier_type or 'VN'}"
    return normalize_generated_message("\r".join([msh, evn, pid, "|".join(pv1_fields)]))


def _patient_account_number(
    get_value: Any,
    session: Session,
    forced_identifier_system: str | None,
    forced_identifier_oid: str | None,
) -> str:
    """Résout PID-18 en privilégiant le dernier dossier du patient."""
    account_number = ""
    patient_id = get_value("id", None)
    if patient_id is not None:
        try:
            dossier = session.exec(
                select(Dossier)
                .where(Dossier.patient_id == patient_id)
                .order_by(Dossier.id.desc())
            ).first()
            if dossier and getattr(dossier, "dossier_seq", None):
                authority, identifier_type = resolve_namespace_authority(
                    session,
                    get_value("entite_juridique_id"),
                    "NDA",
                    forced_identifier_system,
                    forced_identifier_oid,
                )
                account_number = (
                    f"{clean_hl7_value(str(dossier.dossier_seq))}^^^"
                    f"{authority or clean_hl7_value('HOSP')}^{identifier_type or 'AN'}"
                )
        except Exception:
            logger.exception("Failed to resolve dossier/account_number for PID-18")
    if account_number:
        return account_number
    authority, identifier_type = resolve_namespace_authority(
        session,
        get_value("entite_juridique_id"),
        "NDA",
        forced_identifier_system,
        forced_identifier_oid,
    )
    fallback_value = clean_hl7_value(str(get_value("patient_seq") or get_value("id") or "PENDING"))
    return f"{fallback_value}^^^{authority or clean_hl7_value('HOSP')}^{identifier_type or 'AN'}"
