"""Non-regression de capacité du moteur de scénarios multi-endpoints."""

from time import monotonic

import pytest
from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlayStep
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_play_service import prepare_scenario_play


@pytest.mark.performance
@pytest.mark.slow
def test_prepare_large_scenario_for_three_destinations(session, tmp_path):
    """Cent vingt messages vers trois cibles restent préparables en temps borné."""
    scenario = InteropScenario(
        key="scenario-play-performance",
        name="Scénario de charge",
        protocol="HL7",
    )
    session.add(scenario)
    session.commit()
    session.refresh(scenario)

    session.add_all(
        [
            InteropScenarioStep(
                scenario_id=scenario.id,
                order_index=index,
                message_format="hl7",
                message_type="ORU^R01",
                payload=(
                    "MSH|^~\\&|PERF|SRC|TARGET|DST|20260913080000||"
                    f"ORU^R01|PERF-{index}|P|2.5\r"
                    "PID|||PERF-PATIENT"
                ),
            )
            for index in range(1, 121)
        ]
    )
    endpoints = [
        SystemEndpoint(
            name=f"Cible {index}",
            kind="FILE",
            role="sender",
            outbox_path=str(tmp_path / f"target-{index}"),
        )
        for index in range(1, 4)
    ]
    session.add_all(endpoints)
    session.commit()

    started_at = monotonic()
    play = prepare_scenario_play(session, scenario, endpoints, dry_run=True)
    elapsed = monotonic() - started_at

    play_steps = session.exec(
        select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)
    ).all()
    deliveries = session.exec(
        select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)
    ).all()
    assert len(play_steps) == 120
    assert len(deliveries) == 360
    assert all(item.validation_status == "valid" for item in deliveries)
    assert elapsed < 15, f"Préparation trop lente : {elapsed:.2f} s"
