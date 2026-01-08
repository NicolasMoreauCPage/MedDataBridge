"""
Service de gestion des valeurs par défaut pour les mappings de vocabulaires.

Fournit des valeurs par défaut contextuelles quand un mapping n'existe pas
entre les systèmes de vocabulaire.
"""
from typing import Optional, Dict, Any


# Valeurs par défaut par domaine et système cible
DEFAULT_MAPPINGS = {
    # Patient Class (HL7 PV1-2 / FHIR Encounter.class)
    "patient-class": {
        "hospitalise": "I",      # Inpatient
        "externe": "O",          # Outpatient
        "urgence": "E",          # Emergency
        "default": "I"           # Valeur par défaut
    },
    "encounter-class": {
        "hospitalise": "IMP",    # Inpatient encounter
        "externe": "AMB",        # Ambulatory
        "urgence": "EMER",       # Emergency
        "default": "IMP"         # Valeur par défaut
    },

    # Fiabilité d'identité (HL7 Table 0445 / FHIR extensions)
    "identity-reliability": {
        "default": "VIDE"        # Fictive par défaut (sécurité)
    },

    # Types d'identifiant (HL7 Table 0203 / FHIR identifier.type)
    "identifier-type": {
        "IPP": "PI",             # Patient Internal ID
        "NDA": "AN",             # Account Number
        "NA": "AN",              # Account Number
        "VN": "VN",              # Visit Number
        "PI": "PI",              # Patient Internal ID
        "PG": "PI",              # Patient Internal ID (approximation)
        "SS": "SS",              # Social Security Number
        "PC": "PPN",             # Passport Number (approximation)
        "NDP": "PI",             # Patient Internal ID (approximation)
        "MVT": "VN",             # Visit Number (approximation)
        "FINESS": "FIN",         # Facility ID (approximation)
        "default": "PI"          # Patient Internal ID par défaut
    },

    # Statuts de localisation (FHIR Location.status)
    "location-status": {
        "default": "active"
    },

    # Modes de localisation (FHIR Location.mode)
    "location-mode": {
        "default": "instance"
    },

    # Priorités de venue (HL7 Table 0027 / FHIR Encounter.priority)
    "encounter-priority": {
        "default": "routine"
    },

    # Statuts d'exécution (FHIR Task.status)
    "execution-status": {
        "default": "completed"
    },

    # Types d'entité (FHIR Resource types)
    "entity-type": {
        "PATIENT": "Patient",
        "DOSSIER": "EpisodeOfCare",
        "VENUE": "Encounter",
        "MOUVEMENT": "Encounter",
        "MESSAGE_HL7": "MessageHeader",
        "RESSOURCE_FHIR": "Resource",
        "default": "Resource"
    }
}


def get_default_value(target_system: str, source_code: Optional[str] = None) -> Optional[str]:
    """
    Retourne la valeur par défaut pour un système cible.

    Args:
        target_system: Nom du système cible (ex: "patient-class-hl7v2", "encounter-class-fhir")
        source_code: Code source optionnel pour mapping spécifique

    Returns:
        Valeur par défaut ou None si pas de valeur par défaut
    """
    # Extraire le domaine de base du système cible
    # Ex: "patient-class-hl7v2" -> "patient-class"
    # Ex: "identity-reliability-hl7v2" -> "identity-reliability"
    parts = target_system.split('-')
    if len(parts) >= 2:
        base_domain = '-'.join(parts[:-1])  # Tout sauf le dernier élément
    else:
        base_domain = target_system
    
    if base_domain not in DEFAULT_MAPPINGS:
        return None

    system_defaults = DEFAULT_MAPPINGS[base_domain]

    # Essayer d'abord un mapping spécifique
    if source_code and source_code in system_defaults:
        return system_defaults[source_code]

    # Sinon retourner la valeur par défaut générale
    return system_defaults.get("default")


def get_available_defaults() -> Dict[str, Dict[str, Any]]:
    """
    Retourne toutes les valeurs par défaut disponibles.

    Returns:
        Dictionnaire des valeurs par défaut par système
    """
    return DEFAULT_MAPPINGS.copy()


def is_default_available(target_system: str, source_code: Optional[str] = None) -> bool:
    """
    Vérifie si une valeur par défaut est disponible.

    Args:
        target_system: Nom du système cible (ex: "patient-class-hl7v2", "encounter-class-fhir")
        source_code: Code source optionnel

    Returns:
        True si une valeur par défaut existe
    """
    return get_default_value(target_system, source_code) is not None