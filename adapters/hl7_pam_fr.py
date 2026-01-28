"""
Génération de messages HL7 PAM spécifiques au profil France.

Ce module fournit une implémentation par défaut de `build_message_for_movement`
afin que l'import dynamique réalisé dans `app.services.pam` ne lève plus
`ModuleNotFoundError` lors des tests en local.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _format_ts(value: datetime | None) -> str:
    if not value:
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return value.strftime("%Y%m%d%H%M%S")


def build_message_for_movement(
    *,
    dossier: Any,
    venue: Any,
    movement: Any,
    patient: Any,
    movement_namespace: Any = None,
) -> str:
    """
    Construit un message HL7 minimal pour un mouvement patient.
    
    Args:
        dossier: Dossier patient
        venue: Venue/séjour
        movement: Mouvement patient
        patient: Patient
        movement_namespace: Namespace pour l'identifiant du mouvement (optionnel)
    
    Returns:
        Message HL7 PAM avec segment ZBE pour le mouvement
    """
    when = _format_ts(getattr(movement, "when", None))
    control_id = getattr(movement, "mouvement_seq", getattr(movement, "id", ""))
    location = (
        getattr(movement, "location", None)
        or getattr(venue, "code", None)
        or "UNKNOWN"
    )
    uf_responsabilite = (
        getattr(venue, "uf_responsabilite", None)
        or getattr(dossier, "uf_responsabilite", None)
        or "UF-UNKNOWN"
    )

    # MSH complet
    msh = (
        "MSH|^~\\&|POC|POC|DST|DST|"
        f"{when}||ADT^{movement.type or 'A02'}|{control_id}|P|2.5^FRA^2.11.1||||||UNICODE UTF-8"
    )

    # EVN (event type, datetime)
    evn = f"EVN|{movement.type or 'A02'}|{when}"

    # PID complet (exemple simplifié, à enrichir selon spec)
    pid_3 = getattr(patient, 'identifier', None) or getattr(patient, 'external_id', None) or f"PID{getattr(patient, 'id', '')}"
    pid_5 = f"{getattr(patient, 'family', '')}^{getattr(patient, 'given', '')}"
    pid_6 = getattr(patient, 'mother_name', '')
    pid_7 = getattr(patient, 'birth_date', '')
    pid_8 = getattr(patient, 'gender', '')
    pid_11 = getattr(patient, 'address', '')
    pid_15 = getattr(patient, 'primary_language', '')
    pid_16 = getattr(patient, 'marital_status', '')
    pid_18 = getattr(patient, 'account_number', '')
    pid_32 = getattr(patient, 'identity_reliability_code', '')
    pid_fields = [
        "PID", "1", "", pid_3, "", pid_5, pid_6, pid_7, pid_8, "", "", pid_11
    ]
    # Remplir jusqu'à PID-15
    while len(pid_fields) < 15:
        pid_fields.append("")
    pid_fields.append(pid_15)  # PID-15
    pid_fields.append(pid_16)  # PID-16
    # Remplir jusqu'à PID-18
    while len(pid_fields) < 18:
        pid_fields.append("")
    pid_fields.append(pid_18)  # PID-18
    # Remplir jusqu'à PID-32
    while len(pid_fields) < 32:
        pid_fields.append("")
    pid_fields.append(pid_32)  # PID-32
    pid = "|".join(pid_fields)

    # PV1 (champs principaux)
    pv1_2 = getattr(venue, 'patient_class', 'I')
    pv1_3 = location
    pv1_10 = getattr(venue, 'hospital_service', '')
    pv1_19 = getattr(venue, 'visit_number', '')
    pv1_fields = [
        "PV1", "", pv1_2, pv1_3
    ]
    while len(pv1_fields) < 10:
        pv1_fields.append("")
    pv1_fields.append(pv1_10)  # PV1-10
    while len(pv1_fields) < 19:
        pv1_fields.append("")
    pv1_fields.append(pv1_19)  # PV1-19
    pv1 = "|".join(pv1_fields)

    # ZBE (tous champs)
    movement_id = getattr(movement, "mouvement_seq", getattr(movement, "id", ""))
    if movement_namespace:
        authority = getattr(movement_namespace, "name", "UNKNOWN")
        oid = getattr(movement_namespace, "oid", "")
        zbe_1 = f"{movement_id}^{authority}^{oid}^ISO"
    else:
        zbe_1 = str(movement_id)
    zbe_2 = when
    zbe_3 = getattr(movement, 'end_period', '')
    zbe_4 = getattr(movement, 'action_code', 'INSERT')
    zbe_5 = getattr(movement, 'historic_indicator', 'N')
    zbe_6 = getattr(movement, 'origin_event_code', '')
    zbe_7 = getattr(venue, 'uf_medicale', '')
    zbe_8 = getattr(venue, 'uf_soins', '')
    zbe_9 = getattr(movement, 'nature', 'HMS')
    zbe = f"ZBE|{zbe_1}|{zbe_2}|{zbe_3}|{zbe_4}|{zbe_5}|{zbe_6}|{zbe_7}|{zbe_8}|{zbe_9}"

    # MRG (fusion, optionnel)
    mrg = None
    if hasattr(movement, 'merge_identifiers'):
        mrg_1 = getattr(movement, 'merge_identifiers', '')
        mrg_7 = getattr(movement, 'previous_name', '')
        mrg = f"MRG|{mrg_1}||||||{mrg_7}"

    # NK1 (contact, optionnel)
    nk1 = None
    if hasattr(patient, 'contact_name'):
        nk1_2 = getattr(patient, 'contact_relationship', '')
        nk1_3 = getattr(patient, 'contact_address', '')
        nk1_4 = getattr(patient, 'contact_phone', '')
        nk1 = f"NK1|1|{getattr(patient, 'contact_name', '')}|{nk1_2}|{nk1_3}|{nk1_4}"

    # PD1 (compléments patient, optionnel)
    pd1 = None
    if hasattr(patient, 'lifestyle') or hasattr(patient, 'data_protection'):
        pd1_2 = getattr(patient, 'lifestyle', '')
        pd1_12 = getattr(patient, 'data_protection', '')
        pd1_fields = ["PD1", "", pd1_2]
        while len(pd1_fields) < 12:
            pd1_fields.append("")
        pd1_fields.append(pd1_12)
        pd1 = "|".join(pd1_fields)

    # Construction finale
    segments = [msh, evn, pid, pv1, zbe]
    if mrg:
        segments.append(mrg)
    if nk1:
        segments.append(nk1)
    if pd1:
        segments.append(pd1)
    return "\r".join(segments)

