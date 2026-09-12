"""Tests du moteur de qualification reproductible (sans émission réseau)."""

import json

import pytest
from sqlmodel import Session, select

from app.models_endpoints import SystemEndpoint
from app.models_qualification import QualificationCampaign, QualificationCampaignItem
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models import Patient
from app.services.qualification_engine import evaluate_assertions, run_campaign, run_qualification


def _scenario_with_step(session: Session, *, key: str, preconditions: list | None = None) -> InteropScenario:
    scenario = InteropScenario(
        key=key,
        name="Qualification ADT",
        protocol="HL7",
        preconditions_json=json.dumps(preconditions or [{"type": "endpoint_kind", "equals": "MLLP"}]),
        assertions_json=json.dumps(
            [
                {"type": "run_status", "equals": "dry_run"},
                {"type": "payload_contains", "order_index": 1, "value": "ADT^A01"},
            ]
        ),
    )
    session.add(scenario)
    session.commit()
    step = InteropScenarioStep(
        scenario_id=scenario.id,
        order_index=1,
        message_format="hl7",
        message_type="ADT^A01",
        payload="MSH|^~\\&|SENDER|FAC|RECEIVER|FAC|202608250900||ADT^A01|1|P|2.5\rPID|1||123",
        assertions_json=json.dumps([{"type": "step_status", "equals": "dry_run"}]),
    )
    session.add(step)
    session.commit()
    session.refresh(scenario)
    return scenario


@pytest.mark.asyncio
async def test_qualification_evaluates_scenario_and_step_assertions(session: Session):
    endpoint = SystemEndpoint(name="Qualification MLLP", kind="MLLP", host="localhost", port=2575)
    session.add(endpoint)
    session.commit()
    scenario = _scenario_with_step(session, key="qualification.engine.ok")

    result = await run_qualification(session, scenario, endpoint, dry_run=True)

    assert result["verdict"] == "passed"
    run = session.get(ScenarioExecutionRun, result["run_id"])
    assert run is not None
    assert run.qualification_verdict == "passed"
    assert (run.assertion_total, run.assertion_passed) == (3, 3)
    evidence = json.loads(run.evidence_json)
    assert len(evidence["assertions"]) == 3
    step_log = session.exec(
        select(ScenarioExecutionStepLog).where(ScenarioExecutionStepLog.run_id == run.id)
    ).one()
    assert json.loads(step_log.assertion_results_json)[0]["passed"] is True


@pytest.mark.asyncio
async def test_failed_precondition_is_a_persisted_verdict(session: Session):
    endpoint = SystemEndpoint(name="Qualification FILE", kind="FILE")
    session.add(endpoint)
    session.commit()
    scenario = _scenario_with_step(
        session,
        key="qualification.engine.precondition",
        preconditions=[{"type": "endpoint_kind", "equals": "FHIR"}],
    )

    result = await run_qualification(session, scenario, endpoint, dry_run=True)

    assert result["verdict"] == "failed"
    run = session.get(ScenarioExecutionRun, result["run_id"])
    assert run.status == "error"
    assert run.qualification_verdict == "failed"
    assert run.assertion_total == 3  # endpoint actif + scénario actif + type attendu


@pytest.mark.asyncio
async def test_campaign_aggregates_qualification_verdicts(session: Session):
    endpoint = SystemEndpoint(name="Qualification campaign MLLP", kind="MLLP", host="localhost", port=2575)
    session.add(endpoint)
    session.commit()
    scenario = _scenario_with_step(session, key="qualification.engine.campaign")
    campaign = QualificationCampaign(key="qualification.campaign", name="Campagne de qualification")
    session.add(campaign)
    session.commit()
    session.add(
        QualificationCampaignItem(
            campaign_id=campaign.id,
            scenario_id=scenario.id,
            endpoint_id=endpoint.id,
            order_index=1,
        )
    )
    session.commit()

    campaign_run = await run_campaign(session, campaign, dry_run=True)

    assert campaign_run.status == "passed"
    assert (campaign_run.total_items, campaign_run.passed_items, campaign_run.failed_items) == (1, 1, 0)
    assert json.loads(campaign_run.evidence_json)[0]["verdict"] == "passed"


def test_database_assertions_are_evaluated_on_whitelisted_models(session: Session):
    patient = Patient(patient_seq=7001, identifier="QUAL-IPP", family="DOE", given="Jane")
    session.add(patient)
    session.commit()
    run = ScenarioExecutionRun(scenario_id=1, status="success")
    session.add(run)
    session.commit()
    results = evaluate_assertions(
        run, [],
        [
            {"type": "database_count", "model": "Patient", "where": {"identifier": "QUAL-IPP"}, "equals": 1},
            {"type": "database_field_equals", "model": "Patient", "where": {"identifier": "QUAL-IPP"}, "field": "family", "equals": "DOE"},
        ],
        session=session,
    )
    assert [result.passed for result in results] == [True, True]
