# Table de correspondance type de mouvement <-> standards (HL7, FHIR, etc.)
# Peut être enrichie pour d'autres standards ou codes locaux

MOVEMENT_TYPE_MAPPINGS = {
    # Métier -> HL7 ADT
    "admission": {"hl7": "ADT^A01", "fhir": "admit"},
    "transfert": {"hl7": "ADT^A02", "fhir": "transfer"},
    "sortie": {"hl7": "ADT^A03", "fhir": "discharge"},
    "consultation": {"hl7": "ADT^A04", "fhir": "outpatient"},
    "pre_admission": {"hl7": "ADT^A05", "fhir": "pre-admit"},
    "mutation": {"hl7": "ADT^A06", "fhir": "mutation"},
    "retour": {"hl7": "ADT^A07", "fhir": "return"},
    "annulation_admission": {"hl7": "ADT^A11", "fhir": "cancel-admit"},
    "annulation_transfert": {"hl7": "ADT^A12", "fhir": "cancel-transfer"},
    "annulation_sortie": {"hl7": "ADT^A13", "fhir": "cancel-discharge"},
    "permission": {"hl7": "ADT^A21", "fhir": "leave"},
}

def to_standard_movement_code(metier_code: str, standard: str) -> str:
    """Retourne le code du standard (hl7, fhir, ...) pour un type métier donné."""
    return MOVEMENT_TYPE_MAPPINGS.get(metier_code, {}).get(standard)

def from_standard_movement_code(standard_code: str, standard: str) -> str:
    """Retourne le code métier à partir d'un code standard."""
    for metier, mapping in MOVEMENT_TYPE_MAPPINGS.items():
        if mapping.get(standard) == standard_code:
            return metier
    return None
