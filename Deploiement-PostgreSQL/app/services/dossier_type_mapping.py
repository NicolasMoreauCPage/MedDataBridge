"""
Mappings bidirectionnels: dossier_type ↔ PV1-2 (patient_class)

Ce module fournit les fonctions de transformation entre:
- dossier_type (niveau métier français): HOSPITALISE, EXTERNE, URGENCE
- patient_class/PV1-2 (HL7): I (Inpatient), O (Outpatient), E (Emergency)
"""

from typing import Optional
from app.models import DossierType


def dossier_type_to_patient_class(dossier_type: Optional[str]) -> str:
    """
    Transforme dossier_type (français) en patient_class HL7 (PV1-2).
    
    Mappings:
      HOSPITALISE → I (Inpatient)
      EXTERNE     → O (Outpatient)
      URGENCE     → E (Emergency)
      
    Args:
        dossier_type: DossierType enum value or string representation
        
    Returns:
        str: HL7 patient class code (I, O, E)
    """
    if not dossier_type:
        return "I"  # Default to Inpatient
    
    # Handle DossierType enum or string
    type_str = dossier_type.value if hasattr(dossier_type, "value") else str(dossier_type)
    
    mapping = {
        "HOSPITALISE": "I",
        "EXTERNE": "O",
        "URGENCE": "E",
        "hospitalise": "I",
        "externe": "O",
        "urgence": "E",
        "IMP": "I",  # French code mappings
        "AMB": "O",
        "EMER": "E",
    }
    
    return mapping.get(type_str, "I")


def patient_class_to_dossier_type(patient_class: Optional[str]) -> str:
    """
    Transforme patient_class HL7 (PV1-2) en dossier_type (français).
    
    Mappings (inverse):
      I → HOSPITALISE (Inpatient)
      O → EXTERNE (Outpatient)
      E → URGENCE (Emergency)
      
    Args:
        patient_class: HL7 patient class code (I, O, E, or other)
        
    Returns:
        str: dossier_type value (HOSPITALISE, EXTERNE, URGENCE)
    """
    if not patient_class:
        return "HOSPITALISE"  # Default
    
    patient_class = patient_class.strip().upper()
    
    mapping = {
        "I": "HOSPITALISE",  # Inpatient
        "O": "EXTERNE",      # Outpatient
        "E": "URGENCE",      # Emergency
    }
    
    return mapping.get(patient_class, "HOSPITALISE")


def validate_dossier_type_transition(
    old_type: Optional[str],
    new_type: Optional[str],
    trigger_event: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    Valide qu'une transition de dossier_type est sémantiquement correcte.
    
    Pour A06/A07, PV1-2 DOIT changer:
      A06: transition vers hospitalisation (I)
      A07: transition vers externe (O)
      
    Args:
        old_type: ancien dossier_type
        new_type: nouveau dossier_type
        trigger_event: code HL7 (A06, A07, etc.)
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if old_type == new_type:
        if trigger_event in ["A06", "A07"]:
            return False, f"A06/A07 must change dossier_type: {old_type} → {new_type}"
        # Pour les autres événements, pas de changement c'est OK
        return True, None
    
    # Vérifier les transitions valides pour A06/A07
    if trigger_event == "A06":
        # A06: transfert vers l'hospitalisation
        # Doit aboutir à HOSPITALISE
        if new_type != "HOSPITALISE":
            return False, f"A06 must transition to HOSPITALISE, got {new_type}"
    elif trigger_event == "A07":
        # A07: transfert vers l'externe/sortie
        # Doit aboutir à EXTERNE ou URGENCE
        if new_type not in ["EXTERNE", "URGENCE"]:
            return False, f"A07 must transition to EXTERNE or URGENCE, got {new_type}"
    
    return True, None


def is_pv1_2_change_expected(old_type: Optional[str], new_type: Optional[str]) -> bool:
    """
    Détermine si un changement de PV1-2 est attendu.
    
    Utilisé pour déterminer si un événement doit être A06/A07.
    """
    old_class = dossier_type_to_patient_class(old_type)
    new_class = dossier_type_to_patient_class(new_type)
    return old_class != new_class


def get_expected_trigger_event(old_type: Optional[str], new_type: Optional[str]) -> Optional[str]:
    """
    Détermine le trigger_event attendu pour un changement de dossier_type.
    
    Returns:
        str: "A06" (vers hospitalisation), "A07" (vers externe), ou None
    """
    if old_type == new_type:
        return None
    
    old_class = dossier_type_to_patient_class(old_type)
    new_class = dossier_type_to_patient_class(new_type)
    
    # Déterminer la transition
    if new_class == "I":
        return "A06"  # Vers hospitalisation
    elif new_class in ["O", "E"]:
        return "A07"  # Vers externe/urgence
    
    return None
