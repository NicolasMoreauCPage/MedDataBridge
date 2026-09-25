"""Construction des répétitions CX de PID-3 pour l'émission PAM."""

import logging
from typing import Any

from sqlmodel import Session, select

from app.models.identifiers import Identifier
from app.models_structure import IdentifierNamespace
from app.services.identifier_manager import map_identifier_type_to_hl7_code
from app.services.pam_emission_primitives import clean_hl7_value, safe_query

logger = logging.getLogger(__name__)


def build_pid3_identifiers(
    patient: Any,
    session: Session,
    forced_system: str | None = None,
    forced_oid: str | None = None,
) -> str:
    """Construit PID-3, en préservant l'identifiant métier en première place."""
    def authority(system: str | None, oid: str | None) -> str:
        system = (system or "").strip()
        oid = (oid or "").strip()
        return f"{system}&{oid}&ISO" if system and oid else system

    is_snapshot = isinstance(patient, dict)

    def value(attribute, default=None):
        return patient.get(attribute, default) if is_snapshot else getattr(patient, attribute, default)

    identifiers: list[str] = []
    primary_value = clean_hl7_value(value("identifier"))
    if primary_value:
        primary_identifier = None
        try:
            patient_id = value("id")
            if patient_id:
                primary_identifier = safe_query(
                    session,
                    select(Identifier)
                    .where(Identifier.patient_id == patient_id)
                    .where(Identifier.value == primary_value)
                    .where(Identifier.status == "active"),
                )
        except Exception:
            logger.exception("Impossible de résoudre l'identifiant PID-3 principal")
        if primary_identifier:
            identifiers.append(
                f"{primary_value}^^^{authority(primary_identifier.system, getattr(primary_identifier, 'oid', None))}^"
                f"{map_identifier_type_to_hl7_code(primary_identifier.type)}"
            )
        else:
            identifiers.append(f"{primary_value}^^^{authority(forced_system, forced_oid) or 'HOSP'}^PI")

    internal_value = None
    try:
        internal_id = value("patient_seq") or value("id")
        if internal_id and not primary_value:
            namespace = None
            ej_id = value("entite_juridique_id")
            if ej_id:
                namespace = safe_query(
                    session,
                    select(IdentifierNamespace)
                    .where(IdentifierNamespace.entite_juridique_id == ej_id)
                    .where(IdentifierNamespace.type == "IPP")
                    .where(IdentifierNamespace.is_active.is_(True)),
                )
            namespace_authority = (
                authority(namespace.system, namespace.oid)
                if namespace else authority(forced_system, forced_oid)
            )
            if namespace_authority:
                internal_value = clean_hl7_value(internal_id)
                identifiers.append(f"{internal_value}^^^{namespace_authority}^PI")
    except Exception:
        logger.exception("Impossible de résoudre le namespace IPP")

    external_value = clean_hl7_value(value("external_id"))
    if external_value:
        external_identifier = safe_query(
            session,
            select(Identifier)
            .where(Identifier.patient_id == value("id"))
            .where(Identifier.value == external_value)
            .where(Identifier.status == "active"),
        )
        if external_identifier:
            identifiers.append(
                f"{clean_hl7_value(external_identifier.value)}^^^"
                f"{authority(external_identifier.system, external_identifier.oid)}^"
                f"{map_identifier_type_to_hl7_code(external_identifier.type)}"
            )
        else:
            identifiers.append(f"{external_value}^^^EXTERNAL^PI")

    nir_value = clean_hl7_value(value("nir"))
    if nir_value:
        identifiers.append(f"{nir_value}^^^ASIP-SANTE&1.2.250.1.213.1.4.8&ISO^INS")

    already_added = {str(value("id")), internal_value, primary_value, external_value, nir_value}
    if is_snapshot:
        identifier_list = patient.get("identifiers") or []
    elif getattr(patient, "identifiers", None):
        identifier_list = patient.identifiers
    else:
        identifier_list = session.exec(select(Identifier).where(Identifier.patient_id == value("id"))).all()

    for identifier in identifier_list:
        if isinstance(identifier, dict):
            status, identifier_value = identifier.get("status"), identifier.get("value")
            system, oid, identifier_type = identifier.get("system"), identifier.get("oid"), identifier.get("type")
        else:
            status, identifier_value = getattr(identifier, "status", None), getattr(identifier, "value", None)
            system, oid, identifier_type = getattr(identifier, "system", None), getattr(identifier, "oid", None), getattr(identifier, "type", None)
        if status == "active" and identifier_value not in already_added:
            cleaned_value = clean_hl7_value(identifier_value)
            identifiers.append(
                f"{cleaned_value}^^^{authority(system, oid)}^{map_identifier_type_to_hl7_code(identifier_type)}"
            )
            already_added.add(cleaned_value)

    if not identifiers:
        fallback_value = value("patient_seq") or value("id")
        if fallback_value:
            identifiers.append(
                f"{clean_hl7_value(fallback_value)}^^^{authority(forced_system, forced_oid) or 'HOSP'}^PI"
            )
    return "~".join(identifiers)
