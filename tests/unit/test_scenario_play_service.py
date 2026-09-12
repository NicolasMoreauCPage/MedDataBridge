import asyncio
import json

import pytest

from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlayStep
from app.models_qualification import ScenarioTargetState
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_play_service import ScenarioPlayError, execute_scenario_play, prepare_scenario_play


def _scenario(session):
    scenario = InteropScenario(key="scenario-play-unit", name="Jeu multi-protocoles", protocol="MIXED")
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|OLD|P|2.5\rPID|||OLD-IPP\rPV1||I",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="xml", message_type="HPRIM-CCAM",
            payload="<Acte><IPP>{{patient.ipp}}</IPP><Dossier>{{dossier.nda}}</Dossier></Acte>",
        ),
    ])
    session.commit()
    session.refresh(scenario)
    return scenario


def test_play_compiles_one_identity_and_routes_per_format(session, tmp_path):
    scenario = _scenario(session)
    endpoint = SystemEndpoint(name="Dépôt partenaire", kind="FILE", role="sender", outbox_path=str(tmp_path), target_system_key="PARTNER-A")
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    context = json.loads(play.identity_json)
    steps = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id).order_by(ScenarioPlayStep.order_index)).all()
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()

    assert len(steps) == 2
    assert len(deliveries) == 2
    assert context["identifiers"]["ipp"] in steps[0].compiled_payload
    assert context["identifiers"]["nda"] in steps[0].compiled_payload
    assert context["identifiers"]["ipp"] in steps[1].compiled_payload
    assert {delivery.transport for delivery in deliveries} == {"FILE"}

    executed = asyncio.run(execute_scenario_play(session, play.id))
    assert executed.status == "dry_run"
    assert {item.status for item in session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()} == {"dry_run"}


def test_two_plays_never_reuse_their_generated_identifiers(session, tmp_path):
    scenario = _scenario(session)
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()
    first = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    second = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    first_ids, second_ids = json.loads(first.identity_json)["identifiers"], json.loads(second.identity_json)["identifiers"]
    assert first.play_key != second.play_key
    assert first_ids["ipp"] != second_ids["ipp"]
    assert first_ids["nda"] != second_ids["nda"]


def test_play_rejects_a_selection_without_compatible_endpoint(session):
    scenario = _scenario(session)
    endpoint = SystemEndpoint(name="MLLP uniquement", kind="MLLP", role="sender", host="localhost", port=2575)
    session.add(endpoint)
    session.commit()
    with pytest.raises(ScenarioPlayError, match="Aucun endpoint compatible"):
        prepare_scenario_play(session, scenario, [endpoint], dry_run=True)


def test_legacy_hprim_prefix_and_variables_are_normalized_and_update_target_state(session, tmp_path):
    scenario = InteropScenario(key="legacy-hprim-play", name="HPRIM historique", protocol="HPRIM")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id, order_index=1, message_format="hprimxml", message_type="HPRIM",
        payload='MSH|<?xml version="1.0"?><acte><ipp>$NIP$</ipp><dossier>$DOSSIER$</dossier><emetteur>$EMETTEUR$</emetteur></acte>',
    ))
    endpoint = SystemEndpoint(name="Dépôt HPRIM", kind="HPRIM", role="sender", outbox_path=str(tmp_path), target_system_key="GAM-CIBLE")
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint])
    step = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).one()
    assert step.message_format == "xml"
    assert step.compiled_payload.startswith("<acte>")
    assert "$NIP$" not in step.compiled_payload and "$DOSSIER$" not in step.compiled_payload

    asyncio.run(execute_scenario_play(session, play.id))
    state = session.exec(select(ScenarioTargetState).where(ScenarioTargetState.scenario_id == scenario.id)).one()
    assert state.target_system_key == "GAM-CIBLE"
    assert state.status == "success"
    assert state.last_play_id == play.id
