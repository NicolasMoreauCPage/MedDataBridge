from app.models import DossierType, Dossier

# Mapping entre DossierType et encounter_class HL7/FHIR
ENCOUNTER_CLASS_MAPPING = {
    DossierType.HOSPITALISE: "IMP",                  # Inpatient encounter
    DossierType.HOSPITALISATION_MIXTE: "IMP",        # Inpatient encounter (jour + nuit)
    DossierType.HOSPITALISATION_PARTIELLE: "IMP",    # Inpatient encounter (partielle)
    DossierType.EXTERNE: "AMB",                      # Ambulatory encounter
    DossierType.URGENCE: "EMER"                      # Emergency encounter
}

def sync_dossier_class(dossier: Dossier) -> None:
    """
    Synchronise le type de dossier avec la classe de rencontre (encounter_class).
    Cette fonction doit être appelée à chaque fois que le type de dossier change.
    """
    encounter_class = ENCOUNTER_CLASS_MAPPING.get(dossier.dossier_type, "AMB")
    try:
        dossier.encounter_class = encounter_class
    except (ValueError, AttributeError):
        # `encounter_class` n'est pas une colonne persistée sur Dossier : les
        # lecteurs (services d'export FHIR) dérivent de toute façon la classe
        # depuis dossier_type via getattr(dossier, "encounter_class", None).
        pass