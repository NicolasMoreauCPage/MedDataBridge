"""Segments HL7 propres aux messages PAM de mouvement."""

from app.services.vocabulary_translate import map_code


def build_movement_pv1(
    session, mouvement, venue, dossier, timestamp: str,
    resolve_namespace, forced_system: str | None = None, forced_oid: str | None = None,
) -> str:
    """Construit PV1 avec les positions PAM importantes (19, 44 et 52)."""
    if dossier:
        encounter_class = getattr(dossier, "dossier_type", None)
        encounter_class = getattr(encounter_class, "value", encounter_class) or "IMP"
        patient_class = map_code(session, "encounter-class", str(encounter_class), "patient-class")
        if not patient_class:
            patient_class = {
                "hospitalise": "I", "externe": "O", "urgence": "E", "IMP": "I", "AMB": "O", "EMER": "E",
            }.get(str(encounter_class), "I")
    else:
        patient_class = "I"

    location = getattr(mouvement, "location", None) or getattr(mouvement, "to_location", None) or ""
    responsible_unit = getattr(venue, "uf_responsabilite", None) or getattr(dossier, "uf_responsabilite", None) or ""
    visit_value = str(getattr(venue, "venue_seq", None) or getattr(mouvement, "mouvement_seq", None) or "0")
    ej_id = getattr(dossier, "entite_juridique_id", None) or getattr(venue, "entite_juridique_id", None)
    authority, namespace_type = resolve_namespace(session, ej_id, "VN", forced_system, forced_oid)

    fields = [""] * 53
    fields[0], fields[1], fields[2], fields[3] = "PV1", "1", patient_class, location
    fields[19] = f"{visit_value}^^^{authority}^{namespace_type}"
    admission_time = getattr(dossier, "admit_time", None)
    fields[44] = admission_time.strftime("%Y%m%d%H%M%S") if admission_time else timestamp
    fields[52] = responsible_unit
    return "|".join(fields)
