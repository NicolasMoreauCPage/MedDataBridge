"""Service d'import de scénarios depuis JSON.

Permet de recharger des scénarios exportés pour:
- Partager des scénarios entre environnements
- Créer des bibliothèques de scénarios réutilisables
- Restaurer des scénarios archivés
"""

from __future__ import annotations
import json
import re
from typing import Any, Optional
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import GHTContext


class ScenarioImportError(Exception):
    """Erreur lors de l'import d'un scénario."""
    pass


def _normalized_format(value: Optional[str]) -> str:
    value = (value or "hl7").lower()
    return "xml" if value in {"hprim", "hprimxml"} else value


def _message_type(payload: str, message_format: str, fallback: Optional[str]) -> Optional[str]:
    """Déduit un libellé lisible pour une étape issue d'un payload concaténé."""
    if message_format == "xml":
        return fallback or "HPRIM"
    msh = next((line for line in payload.split("\n") if line.startswith("MSH|")), "")
    fields = msh.split("|")
    return fields[8] if len(fields) > 8 and fields[8] else fallback


def split_embedded_messages(
    payload: str, message_format: Optional[str], message_type: Optional[str] = None,
) -> list[dict[str, str | None]]:
    """Sépare les messages HL7/HPRIM concaténés dans une étape historique.

    L'ancien outil pouvait exporter plusieurs ADT suivis d'un HPRIM précédé de
    ``MSH|<?xml`` dans le même champ. Chaque unité devient une étape autonome.
    """
    raw = (payload or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    fmt = _normalized_format(message_format)
    if not raw:
        return [{"payload": raw, "message_format": fmt, "message_type": message_type}]

    # ``MSH|<?xml`` est un préfixe erroné d'export HPRIM et non un MSH HL7.
    marker = re.compile(r"(?m)^MSH\|(?=\^~\\&)|^MSH\|(?=<\?xml)|^<\?xml")
    matches = list(marker.finditer(raw))
    if len(matches) <= 1:
        only_xml = bool(matches and raw[matches[0].start():].startswith(("<?xml", "MSH|<?xml")))
        actual_format = "xml" if only_xml else fmt
        cleaned = re.sub(r"^MSH\|(?=<\?xml)", "", raw) if actual_format == "xml" else raw
        return [{"payload": cleaned, "message_format": actual_format, "message_type": _message_type(cleaned, actual_format, message_type)}]

    messages: list[dict[str, str | None]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        chunk = raw[match.start():end].strip()
        is_xml = chunk.startswith("<?xml") or chunk.startswith("MSH|<?xml")
        actual_format = "xml" if is_xml else "hl7"
        if is_xml:
            chunk = re.sub(r"^MSH\|(?=<\?xml)", "", chunk)
        messages.append({
            "payload": chunk,
            "message_format": actual_format,
            "message_type": _message_type(chunk, actual_format, message_type),
        })
    return messages


def split_embedded_messages_in_scenario(session: Session, scenario: InteropScenario) -> int:
    """Matérialise un message par étape dans un scénario déjà enregistré."""
    originals = list(session.exec(
        select(InteropScenarioStep)
        .where(InteropScenarioStep.scenario_id == scenario.id)
        .order_by(InteropScenarioStep.order_index, InteropScenarioStep.id)
    ).all())
    expanded: list[dict[str, Any]] = []
    for source in originals:
        fragments = split_embedded_messages(source.payload, source.message_format, source.message_type)
        for part_number, fragment in enumerate(fragments, 1):
            label = source.name or source.message_type or "Message"
            expanded.append({
                "name": label if len(fragments) == 1 else f"{label} — message {part_number}",
                "description": source.description,
                "message_format": fragment["message_format"],
                "message_type": fragment["message_type"],
                "payload": fragment["payload"],
                "delay_seconds": source.delay_seconds,
                "assertions_json": source.assertions_json,
                "is_required": source.is_required,
                "route_mode": source.route_mode,
                "endpoint_ids_json": source.endpoint_ids_json,
                "target_system_key": source.target_system_key,
            })
    if len(expanded) == len(originals):
        return 0
    for index, values in enumerate(expanded, 1):
        step = originals[index - 1] if index <= len(originals) else InteropScenarioStep(scenario_id=scenario.id, order_index=index)
        step.order_index = index
        step.name = values["name"]
        step.description = values["description"]
        step.message_format = values["message_format"]
        step.message_type = values["message_type"]
        step.payload = values["payload"]
        step.delay_seconds = values["delay_seconds"]
        step.assertions_json = values["assertions_json"]
        step.is_required = values["is_required"]
        step.route_mode = values["route_mode"]
        step.endpoint_ids_json = values["endpoint_ids_json"]
        step.target_system_key = values["target_system_key"]
        session.add(step)
    session.commit()
    return len(expanded) - len(originals)


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
        functional_comment=json_data.get("functional_comment"),
        category=json_data.get("category"),
        protocol=json_data["protocol"],
        tags=json_data.get("tags"),
        preconditions_json=json_data.get("preconditions_json"),
        assertions_json=json_data.get("assertions_json"),
        expected_outcome_json=json_data.get("expected_outcome_json"),
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
    
    # Déplier les exports historiques qui ont concaténé plusieurs messages.
    # L'ordre du JSON reste la source de vérité, puis chaque fragment reçoit
    # son propre ordre d'émission.
    expanded_steps: list[dict[str, Any]] = []
    for step_data in json_data["steps"]:
        for fragment in split_embedded_messages(
            step_data.get("payload", ""), step_data.get("format", "HL7"), step_data.get("message_type"),
        ):
            expanded_steps.append({**step_data, **fragment})

    # Créer Étape
    for order_index, step_data in enumerate(expanded_steps, 1):
        # Validation Étape
        if "order_index" not in step_data:
            raise ScenarioImportError("Champ 'order_index' manquant dans step")
        if "message_type" not in step_data:
            raise ScenarioImportError(f"Champ 'message_type' manquant dans step {step_data.get('order_index')}")
        if "payload" not in step_data:
            raise ScenarioImportError(f"Champ 'payload' manquant dans step {step_data.get('order_index')}")
        
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=order_index,
            name=step_data.get("name"),
            description=step_data.get("description"),
            message_type=step_data["message_type"],
            message_format=step_data.get("message_format", step_data.get("format", "HL7")),
            delay_seconds=step_data.get("delay_seconds", 0),
            payload=step_data["payload"],
            assertions_json=step_data.get("assertions_json"),
            is_required=step_data.get("is_required", True),
            route_mode=step_data.get("route_mode", "all_compatible"),
            endpoint_ids_json=json.dumps(step_data.get("endpoint_ids", [])) if step_data.get("route_mode") == "explicit" else None,
            target_system_key=step_data.get("target_system_key"),
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
    
    # Vérifier Étape
    if not isinstance(json_data["steps"], list):
        return False, "Le champ 'steps' doit être une liste"
    
    # Un scénario peut avoir 0 Étape (rare mais valide)
    if len(json_data["steps"]) == 0:
        return True, None
    
    # Valider chaque Étape
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
