"""Application des extensions françaises PAM aux entités métier."""
from __future__ import annotations

from typing import Optional

from app.models import Mouvement, Patient
from app.infrastructure.hl7.parsing.french_extension_parser import (
    parse_zfd, parse_zfa, parse_zfp, parse_zfv, parse_rol_segments,
    ROL_ROLE_ODRP, ROL_ROLE_SUBSTITUTE,
)

def _apply_french_extension_segments_to_patient(patient: "Patient", message: Optional[str]) -> None:
    """Applique sur un Patient les champs extraits des segments ZFD/ZFA/ZFP/ROL (ODRP/SUBS)
    d'un message IHE PAM France, quand ce message en contient. No-op si `message` est None
    ou ne contient aucun de ces segments (retour de parse_* à None/liste vide, champs None).
    """
    if not message:
        return
    zfd = parse_zfd(message)
    if zfd:
        if zfd.get("sms_consent") is not None:
            patient.sms_consent = zfd["sms_consent"]
        if zfd.get("birth_date_modified_indicator") is not None:
            patient.birth_date_modified_indicator = zfd["birth_date_modified_indicator"]
        if zfd.get("identity_capture_mode") is not None:
            patient.identity_capture_mode = zfd["identity_capture_mode"]
        if zfd.get("ins_last_query_date") is not None:
            patient.ins_last_query_date = zfd["ins_last_query_date"]
        if zfd.get("identity_proof_type") is not None:
            patient.identity_proof_type = zfd["identity_proof_type"]
        if zfd.get("identity_proof_expiry_date") is not None:
            patient.identity_proof_expiry_date = zfd["identity_proof_expiry_date"]

    zfa = parse_zfa(message)
    if zfa:
        if zfa.get("dmp_status") is not None:
            patient.dmp_status = zfa["dmp_status"]
        if zfa.get("dmp_status_date") is not None:
            patient.dmp_status_date = zfa["dmp_status_date"]
        if zfa.get("dmp_closure_date") is not None:
            patient.dmp_closure_date = zfa["dmp_closure_date"]
        if zfa.get("dmp_feed_opposition") is not None:
            patient.dmp_feed_opposition = zfa["dmp_feed_opposition"]
        if zfa.get("dmp_consultation_consent") is not None:
            patient.dmp_consultation_consent = zfa["dmp_consultation_consent"]

    zfp = parse_zfp(message)
    if zfp:
        if zfp.get("socio_professional_activity") is not None:
            patient.socio_professional_activity = zfp["socio_professional_activity"]
        if zfp.get("socio_professional_category") is not None:
            patient.socio_professional_category = zfp["socio_professional_category"]

    for rol in parse_rol_segments(message):
        if rol.get("role_code") not in (ROL_ROLE_ODRP, ROL_ROLE_SUBSTITUTE):
            continue
        name_parts = [p for p in (rol.get("family_name"), rol.get("given_name")) if p]
        if not name_parts:
            continue
        label = " ".join(name_parts)
        if rol.get("role_code") == ROL_ROLE_SUBSTITUTE:
            label = f"{label} (remplaçant)"
        patient.primary_care_provider = label


def _apply_zfv_to_mouvement(mouvement: "Mouvement", message: Optional[str]) -> None:
    """Applique sur un Mouvement les champs extraits du segment ZFV d'un message IHE
    PAM France, quand ce message en contient un. No-op sinon.
    """
    if not message:
        return
    zfv = parse_zfv(message)
    if not zfv:
        return
    if zfv.get("origin_facility_finess") is not None:
        mouvement.origin_facility_finess = zfv["origin_facility_finess"]
    if zfv.get("origin_stay_date") is not None:
        mouvement.origin_stay_date = zfv["origin_stay_date"]
    if zfv.get("discharge_transport_mode") is not None:
        mouvement.discharge_transport_mode = zfv["discharge_transport_mode"]
    if zfv.get("legal_care_mode_code") is not None:
        mouvement.legal_care_mode_code = zfv["legal_care_mode_code"]
    if zfv.get("transport_care_level") is not None:
        mouvement.transport_care_level = zfv["transport_care_level"]

