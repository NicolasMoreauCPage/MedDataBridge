"""Preuve de cohérence d'un jeu PAM + HPRIM vers deux environnements fichier."""

import asyncio
import json

from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlayStep
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_play_service import execute_scenario_play, prepare_scenario_play


def test_mixed_play_keeps_identifiers_across_two_targets_and_regenerates_next_play(session, tmp_path):
    scenario = InteropScenario(key="mixed-roundtrip", name="A28 + acte CCAM", protocol="MIXED")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A28", payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A28|OLD|P|2.5\rPID|||OLD-IPP\rPV1||N"),
        InteropScenarioStep(scenario_id=scenario.id, order_index=2, message_format="xml", message_type="HPRIM-CCAM", payload="<evenementsServeurActes><patient><identifiant><valeur>{{patient.ipp}}</valeur></identifiant></patient><dossier>{{dossier.nda}}</dossier><venue><valeur>{{venue.id}}</valeur></venue></evenementsServeurActes>"),
    ])
    pam_target = SystemEndpoint(name="GHT B PAM", kind="FILE", role="sender", outbox_path=str(tmp_path / "ght-b-pam"), target_system_key="GHT-B")
    hprim_target = SystemEndpoint(name="GHT B HPRIM", kind="HPRIM", role="sender", outbox_path=str(tmp_path / "ght-b-hprim"), target_system_key="GHT-B")
    session.add_all([pam_target, hprim_target])
    session.commit()

    first = prepare_scenario_play(session, scenario, [pam_target, hprim_target])
    first_ids = json.loads(first.identity_json)["identifiers"]
    asyncio.run(execute_scenario_play(session, first.id))
    compiled = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == first.id)).all()
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == first.id)).all()

    assert all(item.status in {"sent", "skipped"} for item in deliveries)
    assert first_ids["ipp"] in next(item.compiled_payload for item in compiled if item.message_format == "hl7")
    assert first_ids["ipp"] in next(item.compiled_payload for item in compiled if item.message_format == "xml")
    assert first_ids["nda"] in next(item.compiled_payload for item in compiled if item.message_format == "xml")
    assert first_ids["venue"] in next(item.compiled_payload for item in compiled if item.message_format == "xml")
    assert list((tmp_path / "ght-b-pam").glob("*.hl7"))
    assert list((tmp_path / "ght-b-hprim").glob("*.xml"))

    second = prepare_scenario_play(session, scenario, [pam_target, hprim_target], dry_run=True)
    second_ids = json.loads(second.identity_json)["identifiers"]
    assert (first_ids["ipp"], first_ids["nda"], first_ids["venue"]) != (second_ids["ipp"], second_ids["nda"], second_ids["venue"])
