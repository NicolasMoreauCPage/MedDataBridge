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
    # Extract trigger from movement.type if it contains ADT^ prefix
    msg_type = movement.type or 'ADT^A02'
    if '^' in msg_type:
        trigger = msg_type.split('^')[1]
    else:
        trigger = msg_type or 'A02'
    
    msh = (
        "MSH|^~\\&|POC|POC|DST|DST|"
        f"{when}||ADT^{trigger}|{control_id}|P|2.5^FRA^2.11.1||||||UNICODE UTF-8"
    )

    # EVN (event type, datetime)
    evn = f"EVN|{trigger}|{when}"

    # PID complet (exemple simplifié, à enrichir selon spec)
    # PID-3: Format CX (Composite ID) per HL7 v2.5 IHE PAM spec
    # Format: ID^Check Digit^Check Digit Scheme^Assigning Authority^Identifier Type Code
    patient_id = getattr(patient, 'identifier', None) or getattr(patient, 'external_id', None) or f"PID{getattr(patient, 'id', '')}"
    pid_3 = f"{patient_id}^^^SRC-PAM&1.2.250.1.211.99.1&ISO^PI"
    pid_5 = f"{getattr(patient, 'family', '')}^{getattr(patient, 'given', '')}"
    pid_6 = getattr(patient, 'mother_name', '') or ''
    pid_7 = getattr(patient, 'birth_date', '') or ''
    # Format birth_date if it's a date object
    if pid_7:
        if hasattr(pid_7, 'strftime'):
            pid_7 = pid_7.strftime('%Y%m%d')
        else:
            pid_7 = str(pid_7).replace('-', '')
    pid_8 = getattr(patient, 'gender', '') or ''
    pid_11 = getattr(patient, 'address', '') or ''
    pid_15 = getattr(patient, 'primary_language', '') or ''
    pid_16 = getattr(patient, 'marital_status', '') or ''
    pid_18 = getattr(patient, 'account_number', '') or ''
    pid_32 = getattr(patient, 'identity_reliability_code', '') or ''
    # Ensure all pid_fields are strings and convert None to empty string
    def _safe_str(v):
        if v is None:
            return ""
        return str(v)
    
    pid_fields = [
        "PID", "1", "", _safe_str(pid_3), "", _safe_str(pid_5), _safe_str(pid_6), _safe_str(pid_7), _safe_str(pid_8), "", "", _safe_str(pid_11)
    ]
    # Remplir jusqu'à PID-15
    while len(pid_fields) < 15:
        pid_fields.append("")
    pid_fields.append(_safe_str(pid_15))  # PID-15
    pid_fields.append(_safe_str(pid_16))  # PID-16
    # Remplir jusqu'à PID-18
    while len(pid_fields) < 18:
        pid_fields.append("")
    pid_fields.append(_safe_str(pid_18))  # PID-18
    # Remplir jusqu'à PID-32
    while len(pid_fields) < 32:
        pid_fields.append("")
    pid_fields.append(_safe_str(pid_32))  # PID-32
    pid = "|".join(pid_fields)

    # PV1 (champs principaux)
    pv1_2 = getattr(venue, 'patient_class', 'I') or 'I'
    pv1_3 = location or ''
    pv1_10 = getattr(venue, 'hospital_service', '') or ''
    pv1_19 = getattr(venue, 'visit_number', '') or ''
    pv1_fields = [
        "PV1", "", _safe_str(pv1_2), _safe_str(pv1_3)
    ]
    while len(pv1_fields) < 10:
        pv1_fields.append("")
    pv1_fields.append(_safe_str(pv1_10))  # PV1-10
    while len(pv1_fields) < 19:
        pv1_fields.append("")
    pv1_fields.append(_safe_str(pv1_19))  # PV1-19
    pv1 = "|".join(pv1_fields)

    # ZBE (tous champs)
    movement_id = getattr(movement, "mouvement_seq", getattr(movement, "id", ""))
    if movement_namespace:
        authority = getattr(movement_namespace, "name", "UNKNOWN")
        oid = getattr(movement_namespace, "oid", "")
        zbe_1 = f"{movement_id}^{authority}^{oid}^ISO"
    else:
        zbe_1 = str(movement_id)
    zbe_2 = when or ''
    zbe_3 = getattr(movement, 'end_period', '') or ''
    if zbe_3 and hasattr(zbe_3, 'strftime'):
        zbe_3 = zbe_3.strftime('%Y%m%d%H%M%S')
    zbe_4 = getattr(movement, 'action_code', 'INSERT') or 'INSERT'
    zbe_5 = getattr(movement, 'historic_indicator', 'N') or 'N'
    zbe_6 = getattr(movement, 'origin_event_code', '') or ''
    zbe_7 = getattr(venue, 'uf_medicale', '') or ''
    zbe_8 = getattr(venue, 'uf_soins', '') or ''
    zbe_9 = getattr(movement, 'nature', 'HMS') or 'HMS'
    zbe = f"ZBE|{_safe_str(zbe_1)}|{_safe_str(zbe_2)}|{_safe_str(zbe_3)}|{_safe_str(zbe_4)}|{_safe_str(zbe_5)}|{_safe_str(zbe_6)}|{_safe_str(zbe_7)}|{_safe_str(zbe_8)}|{_safe_str(zbe_9)}"

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

