"""Service d'import de scénarios depuis JSON.

Permet de recharger des scénarios exportés pour:
- Partager des scénarios entre environnements
- Créer des bibliothèques de scénarios réutilisables
- Restaurer des scénarios archivés
"""

from __future__ import annotations
from typing import Optional
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure_fhir import GHTContext


class ScenarioImportError(Exception):
    """Erreur lors de l'import d'un scénario."""
    pass


def import_scenario_from_json(
    session: Session,
    json_data: dict,
    ght_context_id: int,
    override_key: Optional[str] = None,
    override_name: Optional[str] = None
) -> InteropScenario:
    """Importe un scénario depuis un export JSON.
    
    Args:
        session: Session DB
        json_data: Dictionnaire JSON du scénario exporté
        ght_context_id: ID du contexte GHT cible
        override_key: Si fourni, remplace la clé du scénario (évite collisions)
        override_name: Si fourni, remplace le nom
        
    Returns:
        Le scénario créé et persisté
        
    Raises:
        ScenarioImportError: Si l'import échoue (données manquantes, clé existante, etc.)
    """
    # Validation données requises
    if "key" not in json_data:
        raise ScenarioImportError("Champ 'key' manquant dans JSON")
    if "name" not in json_data:
        raise ScenarioImportError("Champ 'name' manquant dans JSON")
    if "protocol" not in json_data:
        raise ScenarioImportError("Champ 'protocol' manquant dans JSON")
    if "steps" not in json_data or not isinstance(json_data["steps"], list):
        raise ScenarioImportError("Champ 'steps' manquant ou invalide")
    
    # Vérifier que le contexte existe
    context = session.get(GHTContext, ght_context_id)
    if not context:
        raise ScenarioImportError(f"Contexte GHT {ght_context_id} introuvable")
    
    # Vérifier collision de clé
    scenario_key = override_key or json_data["key"]
    existing = session.exec(
        select(InteropScenario).where(InteropScenario.key == scenario_key)
    ).first()
    if existing:
        raise ScenarioImportError(f"Un scénario avec la clé '{scenario_key}' existe déjà")
    
    # Extraire time_config si présent
    time_config = json_data.get("time_config", {})
    
    # Créer scénario
    scenario_name = override_name or json_data["name"]
    
    # Convertir jitter_events booléen en string pour la base (bug du modèle)
    jitter_events = time_config.get("jitter_events")
    if isinstance(jitter_events, bool):
        jitter_events = "1" if jitter_events else "0"
    
    scenario = InteropScenario(
        key=scenario_key,
        name=scenario_name,
        description=json_data.get("description"),
        category=json_data.get("category"),
        protocol=json_data["protocol"],
        tags=json_data.get("tags"),
        ght_context_id=ght_context_id,
        # Time config
        time_anchor_mode=time_config.get("anchor_mode"),
        time_anchor_days_offset=time_config.get("anchor_days_offset"),
        time_fixed_start_iso=time_config.get("fixed_start_iso"),
        preserve_intervals=time_config.get("preserve_intervals", True),
        jitter_min_minutes=time_config.get("jitter_min"),
        jitter_max_minutes=time_config.get("jitter_max"),
        apply_jitter_on_events=jitter_events,
    )
    
    session.add(scenario)
    
    try:
        session.commit()
        session.refresh(scenario)
    except IntegrityError as e:
        session.rollback()
        raise ScenarioImportError(f"Erreur d'intégrité lors de la création: {str(e)}")
    
    # Créer steps
    for step_data in json_data["steps"]:
        # Validation step
        if "order_index" not in step_data:
            raise ScenarioImportError(f"Champ 'order_index' manquant dans step")
        if "message_type" not in step_data:
            raise ScenarioImportError(f"Champ 'message_type' manquant dans step {step_data.get('order_index')}")
        if "payload" not in step_data:
            raise ScenarioImportError(f"Champ 'payload' manquant dans step {step_data.get('order_index')}")
        
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=step_data["order_index"],
            message_type=step_data["message_type"],
            message_format=step_data.get("format", "HL7"),
            delay_seconds=step_data.get("delay_seconds", 0),
            payload=step_data["payload"],
        )
        session.add(step)
    
    session.commit()
    return scenario


def validate_scenario_json(json_data: dict) -> tuple[bool, Optional[str]]:
    """Valide la structure d'un JSON de scénario avant import.
    
    Returns:
        (is_valid, error_message)
    """
    # Champs requis racine
    required_fields = ["key", "name", "protocol", "steps"]
    for field in required_fields:
        if field not in json_data:
            return False, f"Champ requis manquant: '{field}'"
    
    # Vérifier steps
    if not isinstance(json_data["steps"], list):
        return False, "Le champ 'steps' doit être une liste"
    
    # Un scénario peut avoir 0 steps (rare mais valide)
    if len(json_data["steps"]) == 0:
        return True, None
    
    # Valider chaque step
    for i, step in enumerate(json_data["steps"]):
        if not isinstance(step, dict):
            return False, f"Step {i} n'est pas un objet valide"
        
        step_required = ["order_index", "message_type", "payload"]
        for field in step_required:
            if field not in step:
                return False, f"Step {i}: champ requis manquant '{field}'"
        
        # Vérifier types
        if not isinstance(step["order_index"], int):
            return False, f"Step {i}: 'order_index' doit être un entier"
        if not isinstance(step["payload"], str):
            return False, f"Step {i}: 'payload' doit être une chaîne"
    
    # Vérifier time_config si présent
    if "time_config" in json_data:
        tc = json_data["time_config"]
        if not isinstance(tc, dict):
            return False, "'time_config' doit être un objet"
        
        # Valider types optionnels
        if "anchor_days_offset" in tc and not isinstance(tc["anchor_days_offset"], (int, type(None))):
            return False, "'anchor_days_offset' doit être un entier ou null"
        if "preserve_intervals" in tc and not isinstance(tc["preserve_intervals"], bool):
            return False, "'preserve_intervals' doit être un booléen"
    
    return True, None
