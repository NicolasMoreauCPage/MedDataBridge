"""Configuration automatique d'intervalles temporels réalistes pour scénarios hospitaliers.

Ce module analyse la séquence des événements HL7 dans un scénario et configure
automatiquement des intervalles temporels réalistes basés sur les workflows hospitaliers typiques.
"""
from typing import List, Optional, Tuple, Dict
from datetime import timedelta
from dataclasses import dataclass

from app.services.scenario_timeplan import TimeShiftConfig

@dataclass
class HospitalWorkflowConfig:
    """Configuration temporelle pour un workflow hospitalier spécifique."""
    name: str
    description: str
    anchor_mode: str = "admission_minus_days"
    anchor_days_offset: int = 3  # Par défaut, admission il y a 3 jours
    jitter_min_minutes: int = 5
    jitter_max_minutes: int = 30
    jitter_events: List[str] = None
    # Intervalles entre événements consécutifs (en minutes)
    typical_intervals: Dict[Tuple[str, str], Tuple[int, int]] = None  # (event_from, event_to) -> (min_minutes, max_minutes)

    def __post_init__(self):
        if self.jitter_events is None:
            self.jitter_events = ["A02", "A03", "A06", "A07", "A08", "A11", "A12", "A13"]
        if self.typical_intervals is None:
            self.typical_intervals = {}


# Configurations prédéfinies pour différents types de workflows hospitaliers
HOSPITAL_WORKFLOWS = {
    "emergency_admission": HospitalWorkflowConfig(
        name="Admission urgence",
        description="Séquence rapide pour admission en urgence",
        anchor_days_offset=1,  # Plus récent pour urgence
        jitter_min_minutes=2,
        jitter_max_minutes=15,
        typical_intervals={
            # Consultation urgence → Admission
            ("A05", "A01"): (30, 120),    # 30min à 2h
            # Admission → Premier transfert (service urgence → service hospitalisation)  
            ("A01", "A02"): (60, 240),    # 1h à 4h
            # Transfert → Transfert (changement de service)
            ("A02", "A02"): (120, 480),   # 2h à 8h
            # Transfert → Sortie
            ("A02", "A03"): (240, 720),   # 4h à 12h
            # Admission → Sortie directe (urgence non hospitalisée)
            ("A01", "A03"): (60, 360),    # 1h à 6h
        }
    ),
    
    "planned_admission": HospitalWorkflowConfig(
        name="Hospitalisation programmée",
        description="Séjour hospitalier planifié avec transferts",
        anchor_days_offset=2,
        jitter_min_minutes=10,
        jitter_max_minutes=45,
        typical_intervals={
            # Consultation → Admission programmée
            ("A05", "A01"): (480, 2880),     # 8h à 2 jours
            # Admission → Premier transfert  
            ("A01", "A02"): (240, 720),      # 4h à 12h
            # Transfert → Transfert
            ("A02", "A02"): (360, 1440),     # 6h à 24h
            # Transfert → Sortie
            ("A02", "A03"): (720, 4320),     # 12h à 3 jours
            # Admission → Sortie (séjour court)
            ("A01", "A03"): (1440, 7200),    # 1 à 5 jours
        }
    ),
    
    "consultation_only": HospitalWorkflowConfig(
        name="Consultation externe",
        description="Consultation sans hospitalisation",
        anchor_mode="now",  # Consultation le jour même
        jitter_min_minutes=5,
        jitter_max_minutes=20,
        typical_intervals={
            # Arrivée → Consultation
            ("A04", "A05"): (15, 60),        # 15min à 1h d'attente
            # Consultation → Départ
            ("A05", "A08"): (30, 90),        # 30min à 1h30 de consultation
            # Arrivée → Départ direct (annulation)
            ("A04", "A08"): (5, 30),         # 5 à 30min
        }
    ),
    
    "long_stay": HospitalWorkflowConfig(
        name="Séjour long",
        description="Hospitalisation de longue durée",
        anchor_days_offset=7,  # Plus ancien pour séjour long
        jitter_min_minutes=30,
        jitter_max_minutes=120,
        typical_intervals={
            # Consultation → Admission
            ("A05", "A01"): (720, 4320),     # 12h à 3 jours
            # Admission → Transfert
            ("A01", "A02"): (1440, 4320),    # 1 à 3 jours
            # Transfert → Transfert
            ("A02", "A02"): (2880, 10080),   # 2 à 7 jours
            # Transfert → Sortie
            ("A02", "A03"): (7200, 21600),   # 5 à 15 jours
            # Admission → Sortie
            ("A01", "A03"): (10080, 43200),  # 7 à 30 jours
        }
    )
}


def extract_event_sequence(messages: List[str], message_types: Optional[List[str]] = None) -> List[str]:
    """Extrait la séquence des codes événements HL7 des messages.
    
    Args:
        messages: Liste des payloads HL7
        message_types: Liste optionnelle des message_type (utilisée comme fallback)
    
    Returns:
        Liste des codes événements (ex: ["A05", "A01", "A03"])
    """
    events = []
    
    # Essayer d'extraire depuis les payloads HL7
    for message in messages:
        if not message or not message.strip():
            continue
            
        for line in message.split("\n"):
            if line.startswith("MSH|"):
                parts = line.split("|")
                if len(parts) > 8:
                    comps = parts[8].split("^")
                    if len(comps) > 1:
                        events.append(comps[1])
                        break
    
    # Fallback: utiliser message_types si aucun événement trouvé dans les payloads
    if not events and message_types:
        for msg_type in message_types:
            if msg_type and "^" in msg_type:
                event_code = msg_type.split("^")[1]
                if event_code:
                    events.append(event_code)
    
    return events


def detect_workflow_type(event_sequence: List[str]) -> str:
    """Détecte automatiquement le type de workflow basé sur la séquence d'événements."""
    if not event_sequence:
        return "planned_admission"
    
    # Analyse des patterns d'événements
    has_admission = "A01" in event_sequence or "A14" in event_sequence or "A28" in event_sequence
    has_consultation = "A05" in event_sequence or "A04" in event_sequence
    has_discharge = "A03" in event_sequence or "A16" in event_sequence
    has_transfers = event_sequence.count("A02") > 1 or "A06" in event_sequence or "A07" in event_sequence
    
    # Consultation seulement (pas d'admission)
    if has_consultation and not has_admission:
        return "consultation_only"
    
    # Urgence : séquence rapide avec consultation puis admission
    if has_consultation and has_admission:
        consultation_idx = next((i for i, e in enumerate(event_sequence) if e in ["A04", "A05"]), -1)
        admission_idx = next((i for i, e in enumerate(event_sequence) if e in ["A01", "A14", "A28"]), -1)
        if consultation_idx >= 0 and admission_idx >= 0 and admission_idx - consultation_idx <= 2:
            return "emergency_admission"
    
    # Séjour long : beaucoup de transferts ou présence d'événements de long séjour
    if has_transfers or event_sequence.count("A02") >= 3:
        return "long_stay"
    
    # Par défaut : hospitalisation programmée
    return "planned_admission"


def create_realistic_timeshift_config(
    messages: List[str],
    message_types: Optional[List[str]] = None,
    workflow_type: Optional[str] = None,
    custom_overrides: Optional[Dict] = None
) -> TimeShiftConfig:
    """Crée une configuration TimeShiftConfig réaliste basée sur l'analyse du workflow.
    
    Args:
        messages: Liste des messages HL7 du scénario
        message_types: Liste optionnelle des message_type (fallback)
        workflow_type: Type de workflow forcé (optionnel, sinon auto-détecté)
        custom_overrides: Surcharges personnalisées (optionnel)
    
    Returns:
        TimeShiftConfig configuré pour des intervalles réalistes
    """
    if not messages and not message_types:
        return TimeShiftConfig()
    
    # Analyse de la séquence d'événements
    event_sequence = extract_event_sequence(messages, message_types)
    
    # Détection automatique du workflow si non spécifié
    if workflow_type is None:
        workflow_type = detect_workflow_type(event_sequence)
    
    # Récupération de la configuration prédéfinie
    workflow_config = HOSPITAL_WORKFLOWS.get(workflow_type, HOSPITAL_WORKFLOWS["planned_admission"])
    
    # Configuration de base
    config = TimeShiftConfig(
        anchor_mode=workflow_config.anchor_mode,
        anchor_days_offset=workflow_config.anchor_days_offset,
        preserve_intervals=True,  # Toujours préserver les intervalles relatifs
        jitter_min_minutes=workflow_config.jitter_min_minutes,
        jitter_max_minutes=workflow_config.jitter_max_minutes,
        jitter_events=workflow_config.jitter_events.copy()
    )
    
    # Application des surcharges personnalisées
    if custom_overrides:
        for key, value in custom_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return config


def suggest_scenario_timing_update(scenario_id: int, messages: List[str], message_types: Optional[List[str]] = None) -> Dict:
    """Suggère les paramètres de timing optimal pour un scénario donné.
    
    Args:
        scenario_id: ID du scénario 
        messages: Liste des payloads HL7
        message_types: Liste optionnelle des message_type (fallback si payloads vides)
    
    Returns:
        Dict contenant les valeurs suggérées pour les champs de timing du scénario
    """
    if not messages and not message_types:
        return {}
    
    event_sequence = extract_event_sequence(messages, message_types)
    workflow_type = detect_workflow_type(event_sequence)
    workflow_config = HOSPITAL_WORKFLOWS[workflow_type]
    
    return {
        "time_anchor_mode": workflow_config.anchor_mode,
        "time_anchor_days_offset": workflow_config.anchor_days_offset,
        "preserve_intervals": True,
        "jitter_min_minutes": workflow_config.jitter_min_minutes,
        "jitter_max_minutes": workflow_config.jitter_max_minutes,
        "apply_jitter_on_events": ",".join(workflow_config.jitter_events),
        # Métadonnées pour information
        "_detected_workflow": workflow_type,
        "_workflow_description": workflow_config.description,
        "_event_sequence": event_sequence
    }


__all__ = [
    "HospitalWorkflowConfig",
    "HOSPITAL_WORKFLOWS", 
    "create_realistic_timeshift_config",
    "suggest_scenario_timing_update",
    "detect_workflow_type",
    "extract_event_sequence"
]