"""Moteur de qualification reproductible pour les scénarios d'interopérabilité.

Les assertions restent déclaratives (JSON) afin que les scénarios puissent être
versionnés et exportés sans exécuter de code arbitraire. Exemples pris en charge::

  {"type": "run_status", "equals": "success"}
  {"type": "step_status", "order_index": 1, "equals": "sent"}
  {"type": "ack_code", "order_index": 1, "equals": "AA"}
  {"type": "payload_contains", "order_index": 1, "value": "ADT^A01"}
  {"type": "minimum_success_steps", "value": 2}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from app.models_endpoints import SystemEndpoint
from app.models.qualification import (
    QualificationCampaign,
    QualificationCampaignItem,
    QualificationCampaignRun,
)
from app.models.scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models import Patient, Dossier, Venue, Mouvement
from app.models.hprim_models import HprimCCAMAct, HprimNGAPAct, HprimExchangeAct
from app.services.scenario_runner import send_scenario
from app.services.scenario_qualification_service import record_target_outcome


@dataclass
class AssertionResult:
    assertion: dict[str, Any]
    passed: bool
    actual: Any
    message: str


_ASSERTION_TYPES = {
    "run_status",
    "minimum_success_steps",
    "maximum_error_steps",
    "step_status",
    "ack_code",
    "payload_contains",
    "database_count",
    "database_field_equals",
}

_DATABASE_MODELS = {
    "Patient": Patient, "Dossier": Dossier, "Venue": Venue, "Mouvement": Mouvement,
    "HprimCCAMAct": HprimCCAMAct, "HprimNGAPAct": HprimNGAPAct, "HprimExchangeAct": HprimExchangeAct,
}

_EXPECTED_OUTCOME_MODES = {"positive", "negative"}


def _json_list(raw: Optional[str], field_name: str) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} doit contenir une liste JSON valide: {exc.msg}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field_name} doit contenir une liste d'objets JSON")
    return value


def _validate_assertions(assertions: list[dict[str, Any]], field_name: str) -> None:
    """Rejette une définition incomplète avant toute émission réseau."""
    for index, assertion in enumerate(assertions, start=1):
        kind = assertion.get("type")
        if kind not in _ASSERTION_TYPES:
            raise ValueError(f"{field_name}[{index}] a un type d'assertion inconnu: {kind}")
        if "equals" not in assertion and "value" not in assertion:
            raise ValueError(f"{field_name}[{index}] doit définir equals ou value")
        if kind in {"minimum_success_steps", "maximum_error_steps"}:
            try:
                int(assertion.get("equals", assertion.get("value")))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name}[{index}] attend un nombre entier") from exc
        if kind in {"database_count", "database_field_equals"}:
            if assertion.get("model") not in _DATABASE_MODELS:
                raise ValueError(f"{field_name}[{index}] référence un modèle BDD non autorisé")
            if not isinstance(assertion.get("where", {}), dict):
                raise ValueError(f"{field_name}[{index}].where doit être un objet")
            if kind == "database_field_equals" and not assertion.get("field"):
                raise ValueError(f"{field_name}[{index}] doit préciser field")


def _expected_outcome(raw: Optional[str]) -> dict[str, Any]:
    """Lit le contrat facultatif d'un scénario positif ou négatif.

    Exemple de test négatif ::

        {"mode":"negative", "ack_codes":["AE", "AR"], "step_order":2}

    Le contrat reste volontairement simple et sérialisable : il peut être
    édité dans l'IHM, exporté et exécuté sans code arbitraire.
    """
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"expected_outcome_json doit être un objet JSON valide: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("expected_outcome_json doit être un objet JSON")
    mode = value.get("mode", "positive")
    if mode not in _EXPECTED_OUTCOME_MODES:
        raise ValueError("expected_outcome_json.mode doit valoir positive ou negative")
    ack_codes = value.get("ack_codes")
    if ack_codes is not None and (
        not isinstance(ack_codes, list) or not all(isinstance(code, str) and code for code in ack_codes)
    ):
        raise ValueError("expected_outcome_json.ack_codes doit être une liste de codes non vides")
    if value.get("step_order") is not None:
        try:
            if int(value["step_order"]) < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("expected_outcome_json.step_order doit être un entier positif") from exc
    if value.get("error_contains") is not None and not isinstance(value["error_contains"], str):
        raise ValueError("expected_outcome_json.error_contains doit être une chaîne")
    if value.get("run_statuses") is not None and (
        not isinstance(value["run_statuses"], list)
        or not all(isinstance(status, str) and status for status in value["run_statuses"])
    ):
        raise ValueError("expected_outcome_json.run_statuses doit être une liste de statuts non vides")
    return value


def evaluate_expected_outcome(
    run: ScenarioExecutionRun,
    step_logs: list[ScenarioExecutionStepLog],
    contract: dict[str, Any],
) -> list[AssertionResult]:
    """Transforme un résultat attendu en preuve de qualification.

    Un scénario négatif est valide lorsqu'il est rejeté par le mécanisme visé,
    optionnellement avec l'ACK et le texte de diagnostic attendus. Il ne faut
    donc plus désactiver un corpus négatif uniquement parce qu'il produit AE
    ou AR : son rejet devient le comportement attendu.
    """
    if not contract:
        return []
    mode = contract.get("mode", "positive")
    selected = step_logs
    if contract.get("step_order") is not None:
        selected = [
            item for item in step_logs
            if item.order_index == int(contract["step_order"])
        ]
    expected_codes = {code.upper() for code in contract.get("ack_codes", [])}
    ack_codes = {str(item.ack_code or "").upper() for item in selected if item.ack_code}
    errors = "\n".join(item.error_message or "" for item in selected)
    rejected = any(
        item.status == "error" or str(item.ack_code or "").upper() in {"AE", "AR"}
        for item in selected
    )
    if mode == "negative":
        passed = bool(selected) and rejected
        if expected_codes:
            passed = passed and bool(expected_codes.intersection(ack_codes))
        expected_text = contract.get("error_contains")
        if expected_text:
            passed = passed and expected_text.lower() in errors.lower()
        actual = {
            "run_status": run.status,
            "step_count": len(selected),
            "ack_codes": sorted(ack_codes),
            "rejected": rejected,
            "errors": errors[:500],
        }
        return [AssertionResult(contract, passed, actual, "Rejet attendu")]

    statuses = set(contract.get("run_statuses", ["success", "dry_run"]))
    passed = run.status in statuses
    if expected_codes:
        passed = passed and expected_codes.issubset(ack_codes)
    expected_text = contract.get("error_contains")
    if expected_text:
        passed = passed and expected_text.lower() in errors.lower()
    actual = {"run_status": run.status, "ack_codes": sorted(ack_codes), "errors": errors[:500]}
    return [AssertionResult(contract, passed, actual, "Résultat attendu")]


def validate_preconditions(scenario: InteropScenario, endpoint: SystemEndpoint) -> list[AssertionResult]:
    """Évalue les préconditions sans déclencher le moindre échange réseau."""
    checks: list[AssertionResult] = [
        AssertionResult({"type": "scenario_active"}, scenario.is_active, scenario.is_active, "Scénario actif"),
        AssertionResult({"type": "endpoint_enabled"}, endpoint.is_enabled, endpoint.is_enabled, "Endpoint activé"),
    ]
    for condition in _json_list(scenario.preconditions_json, "preconditions_json"):
        kind = condition.get("type")
        if kind == "endpoint_kind":
            expected = condition.get("equals")
            actual = endpoint.kind
            checks.append(AssertionResult(condition, actual == expected, actual, f"Type endpoint attendu: {expected}"))
        elif kind == "minimum_steps":
            expected = int(condition.get("value", 1))
            actual = len(scenario.steps or [])
            checks.append(AssertionResult(condition, actual >= expected, actual, f"Au moins {expected} étape(s)"))
        else:
            checks.append(AssertionResult(condition, False, None, f"Précondition inconnue: {kind}"))
    return checks


def _find_step_log(step_logs: list[ScenarioExecutionStepLog], assertion: dict[str, Any]) -> Optional[ScenarioExecutionStepLog]:
    order_index = assertion.get("order_index")
    if order_index is None:
        return step_logs[0] if len(step_logs) == 1 else None
    return next((log for log in step_logs if log.order_index == int(order_index)), None)


def evaluate_assertions(
    run: ScenarioExecutionRun,
    step_logs: list[ScenarioExecutionStepLog],
    assertions: list[dict[str, Any]],
    session: Optional[Session] = None,
) -> list[AssertionResult]:
    """Évalue les assertions d'un run contre ses journaux persistés."""
    results: list[AssertionResult] = []
    for assertion in assertions:
        kind = assertion.get("type")
        expected = assertion.get("equals", assertion.get("value"))
        if kind == "run_status":
            actual = run.status
            passed = actual == expected
        elif kind == "minimum_success_steps":
            actual = run.success_steps
            passed = actual >= int(expected)
        elif kind == "maximum_error_steps":
            actual = run.error_steps
            passed = actual <= int(expected)
        elif kind in {"step_status", "ack_code", "payload_contains"}:
            step_log = _find_step_log(step_logs, assertion)
            if step_log is None:
                actual, passed = None, False
            elif kind == "step_status":
                actual, passed = step_log.status, step_log.status == expected
            elif kind == "ack_code":
                actual, passed = step_log.ack_code, step_log.ack_code == expected
            else:
                actual = step_log.payload_excerpt or ""
                passed = str(expected) in actual
        elif kind in {"database_count", "database_field_equals"}:
            if session is None:
                actual, passed = None, False
            else:
                model = _DATABASE_MODELS[assertion["model"]]
                criteria = assertion.get("where", {})
                records = [
                    record for record in session.exec(select(model)).all()
                    if all(str(getattr(record, key, None)) == str(value) for key, value in criteria.items())
                ]
                if kind == "database_count":
                    actual, passed = len(records), len(records) == int(expected)
                else:
                    actual = getattr(records[0], assertion["field"], None) if records else None
                    passed = actual == expected
        else:
            actual, passed = None, False
        results.append(AssertionResult(assertion, passed, actual, f"Assertion {kind}"))
    return results


async def run_qualification(
    session: Session,
    scenario: InteropScenario,
    endpoint: SystemEndpoint,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Exécute un scénario, évalue ses assertions et conserve les preuves."""
    scenario_assertions = _json_list(scenario.assertions_json, "assertions_json")
    _validate_assertions(scenario_assertions, "assertions_json")
    expected_outcome = _expected_outcome(scenario.expected_outcome_json)
    step_assertions_by_id: dict[int, list[dict[str, Any]]] = {}
    for step in scenario.steps:
        if step.id is None:
            continue
        assertions = _json_list(step.assertions_json, "assertions_json")
        _validate_assertions(assertions, f"étape {step.order_index}.assertions_json")
        step_assertions_by_id[step.id] = assertions

    preconditions = validate_preconditions(scenario, endpoint)
    if not all(result.passed for result in preconditions):
        run = ScenarioExecutionRun(
            scenario_id=scenario.id,
            endpoint_id=endpoint.id,
            status="error",
            total_steps=len(scenario.steps or []),
            finished_at=datetime.utcnow(),
            qualification_verdict="failed",
            assertion_total=len(preconditions),
            assertion_passed=sum(result.passed for result in preconditions),
            evidence_json=json.dumps([asdict(result) for result in preconditions], ensure_ascii=False),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return {"run_id": run.id, "verdict": run.qualification_verdict, "preconditions": [asdict(r) for r in preconditions], "assertions": []}

    await send_scenario(session, scenario, endpoint, dry_run=dry_run)
    run = session.exec(
        select(ScenarioExecutionRun)
        .where(ScenarioExecutionRun.scenario_id == scenario.id)
        .where(ScenarioExecutionRun.endpoint_id == endpoint.id)
        .order_by(ScenarioExecutionRun.id.desc())
    ).first()
    if run is None:
        raise RuntimeError("Le runner n'a pas créé de trace d'exécution")

    step_logs = session.exec(
        select(ScenarioExecutionStepLog)
        .where(ScenarioExecutionStepLog.run_id == run.id)
        .order_by(ScenarioExecutionStepLog.order_index)
    ).all()
    results = evaluate_assertions(run, step_logs, scenario_assertions, session=session)
    results.extend(evaluate_expected_outcome(run, step_logs, expected_outcome))

    # Une assertion définie sur une étape ne doit pas dépendre de l'ordre ou du
    # nombre des autres étapes. On la limite donc à son journal d'exécution et
    # on conserve la preuve directement sur ce journal.
    steps_by_id: dict[int, InteropScenarioStep] = {
        step.id: step for step in scenario.steps if step.id is not None
    }
    for step_log in step_logs:
        step = steps_by_id.get(step_log.step_id)
        if step is None:
            continue
        step_assertions = step_assertions_by_id.get(step.id, [])
        step_results = evaluate_assertions(run, [step_log], step_assertions, session=session)
        step_log.assertion_results_json = json.dumps(
            [asdict(result) for result in step_results], ensure_ascii=False
        )
        session.add(step_log)
        results.extend(step_results)
    verdict = "passed" if all(result.passed for result in results) else "failed"
    # Sans assertion explicite, le transport constitue le verdict minimal.
    if not results:
        verdict = "passed" if run.status in {"success", "dry_run"} else "failed"

    run.qualification_verdict = verdict
    run.assertion_total = len(results)
    run.assertion_passed = sum(result.passed for result in results)
    run.evidence_json = json.dumps(
        {"preconditions": [asdict(r) for r in preconditions], "assertions": [asdict(r) for r in results]},
        ensure_ascii=False,
    )
    session.add(run)
    session.commit()
    if not dry_run:
        record_target_outcome(session, scenario.id, endpoint.target_system_key or endpoint.name, verdict, run_at=run.finished_at)
        session.commit()
    return {"run_id": run.id, "verdict": verdict, "preconditions": [asdict(r) for r in preconditions], "assertions": [asdict(r) for r in results]}


async def run_campaign(session: Session, campaign: QualificationCampaign, *, dry_run: bool = False) -> QualificationCampaignRun:
    """Exécute séquentiellement une campagne et agrège ses preuves."""
    items = session.exec(
        select(QualificationCampaignItem)
        .where(QualificationCampaignItem.campaign_id == campaign.id)
        .where(QualificationCampaignItem.is_active.is_(True))
        .order_by(QualificationCampaignItem.order_index)
    ).all()
    campaign_run = QualificationCampaignRun(campaign_id=campaign.id, total_items=len(items))
    session.add(campaign_run)
    session.commit()
    evidence: list[dict[str, Any]] = []
    for item in items:
        scenario, endpoint = session.get(InteropScenario, item.scenario_id), session.get(SystemEndpoint, item.endpoint_id)
        if not scenario or not endpoint:
            result = {"verdict": "failed", "error": "Scénario ou endpoint introuvable"}
        else:
            try:
                result = await run_qualification(session, scenario, endpoint, dry_run=dry_run)
            except Exception as exc:  # Evidence must survive one bad item.
                result = {"verdict": "failed", "error": str(exc)}
        evidence.append({"item_id": item.id, **result})
    campaign_run.passed_items = sum(item["verdict"] == "passed" for item in evidence)
    campaign_run.failed_items = len(evidence) - campaign_run.passed_items
    campaign_run.status = "passed" if campaign_run.failed_items == 0 else "failed"
    campaign_run.finished_at = datetime.utcnow()
    campaign_run.evidence_json = json.dumps(evidence, ensure_ascii=False)
    session.add(campaign_run)
    session.commit()
    return campaign_run
