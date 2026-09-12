"""Évaluation déclarative des assertions sur un jeu multi-endpoints."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from app.models import Patient, Dossier, Venue, Mouvement
from app.models.hprim_models import HprimCCAMAct, HprimNGAPAct, HprimExchangeAct
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlay, ScenarioPlayStep
from app.models_scenarios import InteropScenario

_MODELS = {
    "Patient": Patient, "Dossier": Dossier, "Venue": Venue, "Mouvement": Mouvement,
    "HprimCCAMAct": HprimCCAMAct, "HprimNGAPAct": HprimNGAPAct, "HprimExchangeAct": HprimExchangeAct,
}


def _assertions(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("assertions_json doit être une liste JSON")
    return value


def _resolve_identity_value(value: Any, play: ScenarioPlay) -> Any:
    """Résout les identifiants du jeu dans les critères d'assertion déclaratifs."""
    if not isinstance(value, str) or "{{" not in value:
        return value
    try:
        identity = json.loads(play.identity_json or "{}")
    except json.JSONDecodeError:
        identity = {}
    identifiers = identity.get("identifiers", {})
    replacements = {
        "{{patient.ipp}}": str(identifiers.get("ipp", "")),
        "{{patient.ins}}": str(identity.get("patient", {}).get("ins", "")),
        "{{dossier.nda}}": str(identifiers.get("nda", "")),
        "{{venue.id}}": str(identifiers.get("venue", "")),
        "{{movement.id}}": str(identity.get("movement", {}).get("id", "")),
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def evaluate_play_assertions(
    session: Session, scenario: InteropScenario, play: ScenarioPlay,
    steps: list[ScenarioPlayStep], deliveries: list[ScenarioDelivery],
) -> list[dict[str, Any]]:
    """Retourne des preuves JSON sans exécuter d'expression arbitraire."""
    results: list[dict[str, Any]] = []
    by_order = {step.order_index: step for step in steps}
    for assertion in _assertions(scenario.assertions_json):
        kind, expected = assertion.get("type"), assertion.get("equals", assertion.get("value"))
        expected = _resolve_identity_value(expected, play)
        actual: Any = None
        if kind == "run_status":
            actual = play.status
        elif kind == "minimum_success_steps":
            actual = sum(delivery.status == "sent" for delivery in deliveries)
            expected = int(expected)
            results.append({"assertion": assertion, "actual": actual, "passed": actual >= expected})
            continue
        elif kind == "maximum_error_steps":
            actual = sum(delivery.status not in {"sent", "skipped", "dry_run"} for delivery in deliveries)
            expected = int(expected)
            results.append({"assertion": assertion, "actual": actual, "passed": actual <= expected})
            continue
        elif kind in {"step_status", "ack_code", "payload_contains"}:
            order = int(assertion.get("order_index", -1))
            step = by_order.get(order)
            related = [delivery for delivery in deliveries if step and delivery.play_step_id == step.id and delivery.status != "skipped"]
            if kind == "step_status":
                actual = "sent" if related and all(item.status in {"sent", "dry_run"} for item in related) else (related[0].status if related else None)
            elif kind == "ack_code":
                actual = next((item.ack_code for item in related if item.ack_code), None)
            else:
                actual = step.compiled_payload if step else ""
                results.append({"assertion": assertion, "actual": actual, "passed": str(expected) in actual})
                continue
        elif kind in {"database_count", "database_field_equals"}:
            model = _MODELS.get(assertion.get("model"))
            if not model:
                results.append({"assertion": assertion, "actual": None, "passed": False, "message": "Modèle BDD non autorisé"})
                continue
            records = [
                record for record in session.exec(select(model)).all()
                if all(
                    str(getattr(record, key, None)) == str(_resolve_identity_value(value, play))
                    for key, value in assertion.get("where", {}).items()
                )
            ]
            if kind == "database_count":
                actual, expected = len(records), int(expected)
            else:
                actual = getattr(records[0], assertion.get("field", ""), None) if records else None
        else:
            results.append({"assertion": assertion, "actual": None, "passed": False, "message": "Type d'assertion inconnu"})
            continue
        results.append({"assertion": assertion, "actual": actual, "passed": actual == expected})
    return results
