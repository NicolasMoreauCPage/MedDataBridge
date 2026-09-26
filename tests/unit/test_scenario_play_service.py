import asyncio
import json
import re
from datetime import datetime, timedelta

import pytest

from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_practitioners import MedecinResponsable
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlayStep
from app.models_outbox import OutboundMessage
from app.models_qualification import ScenarioTargetState
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_play_service import ScenarioPlayError, _adapt_fhir, _adapt_hprim_xml, execute_scenario_play, prepare_scenario_play
from app.services.outbox_service import process_due_messages


def _scenario(session):
    scenario = InteropScenario(key="scenario-play-unit", name="Jeu multi-protocoles", protocol="MIXED")
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|OLD|P|2.5\rPID|||OLD-IPP\rPV1||I|||||99999999999^ANCIEN^MEDECIN||||||||||88888888888^ANCIEN^ADMETTEUR\rROL||UC|AT|77777777777^ANCIEN^ROL\rNTE|1||{{practitioner.rpps}}^{{medecin.nom}}",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="xml", message_type="HPRIM-CCAM",
            payload="<Acte><IPP>{{patient.ipp}}</IPP><Dossier>{{dossier.nda}}</Dossier><Medecin>{{practitioner.rpps}}</Medecin><Nom>{{medecin.nom}}</Nom><medecin><noRPPS>99999999999</noRPPS><numeroAdeli>111111111</numeroAdeli><personne><nomUsuel>ANCIEN</nomUsuel><prenom>MEDECIN</prenom></personne></medecin><patient><personne><nomUsuel>PATIENT</nomUsuel></personne></patient></Acte>",
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
    assert context["practitioner"]["rpps"] in steps[0].compiled_payload
    assert context["practitioner"]["rpps"] in steps[1].compiled_payload
    assert context["practitioner"]["family"] in steps[0].compiled_payload
    assert context["practitioner"]["family"] in steps[1].compiled_payload
    assert "99999999999^ANCIEN^MEDECIN" not in steps[0].compiled_payload
    assert "77777777777^ANCIEN^ROL" not in steps[0].compiled_payload
    assert "99999999999" not in steps[1].compiled_payload
    assert "111111111" not in steps[1].compiled_payload
    assert "<nomUsuel>PATIENT</nomUsuel>" in steps[1].compiled_payload
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


def test_multi_patient_hl7_scenario_keeps_one_generated_identity_per_source_patient(session, tmp_path):
    """Une séquence mère/nouveau-né ne doit pas être aplatie sur une venue."""
    scenario = InteropScenario(key="mother-newborn", name="Mère et nouveau-né", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A28",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A28|1|P|2.5\rPID|||MOTHER",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010001||ADT^A01|2|P|2.5\rPID|||MOTHER\rPV1||I||||||||||||||||MOTHER-NDA",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=3, message_format="hl7", message_type="ADT^A28",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010002||ADT^A28|3|P|2.5\rPID|||BABY",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=4, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010003||ADT^A01|4|P|2.5\rPID|||BABY\rPV1||I||||||||||||||||BABY-NDA",
        ),
    ])
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    context = json.loads(play.identity_json)
    steps = session.exec(
        select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id).order_by(ScenarioPlayStep.order_index)
    ).all()

    mother = context["entities"]["pid:MOTHER"]["identifiers"]
    baby = context["entities"]["pid:BABY"]["identifiers"]
    assert mother["ipp"] != baby["ipp"]
    assert mother["nda"] != baby["nda"]
    assert all(mother["ipp"] in step.compiled_payload for step in steps[:2])
    assert all(baby["ipp"] in step.compiled_payload for step in steps[2:])
    assert mother["ipp"] not in steps[2].compiled_payload
    assert baby["ipp"] not in steps[1].compiled_payload


def test_play_rewrites_zbe6_to_the_regenerated_movement_reference(session, tmp_path):
    scenario = InteropScenario(key="zbe-chain", name="Chaîne ZBE", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|1|P|2.5\rPID|||P\rZBE|SOURCE-1||||",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="hl7", message_type="ADT^A12",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010001||ADT^A12|2|P|2.5\rPID|||P\rZBE|SOURCE-2|||||SOURCE-1",
        ),
    ])
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    steps = session.exec(
        select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id).order_by(ScenarioPlayStep.order_index)
    ).all()
    first_zbe = next(line for line in steps[0].compiled_payload.split("\r") if line.startswith("ZBE|")).split("|")
    second_zbe = next(line for line in steps[1].compiled_payload.split("\r") if line.startswith("ZBE|")).split("|")
    assert first_zbe[1].isdigit()
    assert second_zbe[1].isdigit()
    assert first_zbe[1] != second_zbe[1]
    assert second_zbe[6] == first_zbe[1]


def test_play_assigns_a_distinct_zbe1_to_repeated_source_inserts(session, tmp_path):
    """Les exports CPage peuvent réemployer ZBE-1 pour plusieurs INSERT."""
    scenario = InteropScenario(key="zbe-reused-insert", name="ZBE réutilisé", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|1|P|2.5\rPID|||P\rZBE|SOURCE-1|| |INSERT",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="hl7", message_type="ADT^A02",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010001||ADT^A02|2|P|2.5\rPID|||P\rZBE|SOURCE-1|||INSERT",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=3, message_format="hl7", message_type="ADT^Z99",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010002||ADT^Z99|3|P|2.5\rPID|||P\rZBE|SOURCE-1|||UPDATE",
        ),
    ])
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    steps = session.exec(
        select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id).order_by(ScenarioPlayStep.order_index)
    ).all()
    zbe_ids = [next(line for line in step.compiled_payload.split("\r") if line.startswith("ZBE|")).split("|")[1] for step in steps]

    assert zbe_ids[0].isdigit()
    assert zbe_ids[1].isdigit()
    assert zbe_ids[0] != zbe_ids[1]
    assert zbe_ids[2] == zbe_ids[1]


def test_multi_venue_scenario_keeps_nda_but_regenerates_each_pv119(session, tmp_path):
    scenario = InteropScenario(key="two-visits", name="Deux venues", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|1|P|2.5\rPID|||P|||||||||||||||NDA-1\rPV1||I|||||||||||||||||VISIT-1",
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="hl7", message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010001||ADT^A01|2|P|2.5\rPID|||P|||||||||||||||NDA-1\rPV1||I|||||||||||||||||VISIT-2",
        ),
    ])
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    steps = session.exec(
        select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id).order_by(ScenarioPlayStep.order_index)
    ).all()
    def identifiers(payload):
        lines = payload.split("\r")
        pid = next(line for line in lines if line.startswith("PID|")).split("|")
        pv1 = next(line for line in lines if line.startswith("PV1|")).split("|")
        return pid[18].split("^")[0], pv1[19].split("^")[0]

    first_nda, first_venue = identifiers(steps[0].compiled_payload)
    second_nda, second_venue = identifiers(steps[1].compiled_payload)
    assert first_nda == second_nda
    assert first_venue != second_venue


def test_play_uses_the_active_local_practitioner_for_all_protocols(session, tmp_path):
    scenario = _scenario(session)
    practitioner = MedecinResponsable(
        rpps="12345678901", adeli="123456789", family_name="DUPONT", given_name="Alice", prefix="Dr"
    )
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add_all([practitioner, endpoint])
    session.commit()
    session.refresh(endpoint)

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    context = json.loads(play.identity_json)
    steps = session.exec(
        select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id).order_by(ScenarioPlayStep.order_index)
    ).all()

    assert context["practitioner"]["rpps"] == "12345678901"
    assert context["practitioner"]["family"] == "DUPONT"
    assert context["practitioner"]["xcn"].startswith("12345678901^DUPONT^Alice")
    assert all("12345678901" in step.compiled_payload for step in steps)


def test_fhir_practitioner_is_replaced_by_the_play_practitioner():
    adapted = _adapt_fhir(
        {
            "resourceType": "Practitioner",
            "identifier": [{"system": "urn:old", "value": "99999999999"}],
            "name": [{"family": "ANCIEN", "given": ["MEDECIN"]}],
        },
        {
            "{{practitioner.rpps}}": "12345678901",
            "{{practitioner.adeli}}": "123456789",
            "{{practitioner.family}}": "DUPONT",
            "{{practitioner.given}}": "Alice",
            "{{practitioner.prefix}}": "Dr",
        },
    )

    assert adapted["identifier"] == [
        {"system": "urn:oid:1.2.250.1.71.4.2.1", "value": "12345678901"},
        {"system": "urn:oid:1.2.250.1.71.4.2.1.1", "value": "123456789"},
    ]
    assert adapted["name"][0]["family"] == "DUPONT"
    assert adapted["name"][0]["given"] == ["Alice"]


def test_literal_json_hl7_separators_are_normalized_before_practitioner_projection(session, tmp_path):
    scenario = InteropScenario(key="literal-cr", name="Séparateurs JSON", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01",
        payload=r"MSH|^~\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|OLD|P|2.5\rPID|||OLD\rPV1||I|||||99999999999^ANCIEN^MEDECIN",
    ))
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    step = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).one()
    context = json.loads(play.identity_json)

    assert "\\r" not in step.compiled_payload
    assert context["practitioner"]["rpps"] in step.compiled_payload
    assert "99999999999^ANCIEN^MEDECIN" not in step.compiled_payload


def test_play_completes_missing_required_msh_sender_fields(session, tmp_path):
    """Un A28 historique sans MSH-3 doit rester émissible et valide en HL7."""
    scenario = InteropScenario(key="msh-sender", name="En-tête historique incomplet", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A28",
        payload="MSH|^~\\&||SRC-FAC|DST|DST-FAC|202601010000||ADT^A28|OLD|P|2.5\rPID|||OLD-IPP",
    ))
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    step = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).one()

    assert step.compiled_payload.split("\r", 1)[0].split("|")[2] == "MEDBRIDGE"
    assert step.compiled_payload.split("\r", 1)[0].split("|")[3] == "SRC-FAC"


def test_hprim_ngap_generic_legacy_act_token_is_made_valid_for_ngap():
    compiled = _adapt_hprim_xml(
        "<evenementsServeurActes><lettreCle>TEST001</lettreCle></evenementsServeurActes>",
        {
            "{{hprim.message_id}}": "H1", "{{patient.ipp}}": "IPP1", "{{venue.id}}": "V1",
            "{{target.uf.code}}": "UF1", "{{practitioner.rpps}}": "12345678901",
            "{{practitioner.adeli}}": "123456789", "{{practitioner.family}}": "DUPONT",
            "{{practitioner.given}}": "Alice",
        },
    )

    assert "<lettreCle>AMK</lettreCle>" in compiled


def test_hprim_adaptation_rejects_doctype():
    with pytest.raises(ScenarioPlayError, match="DOCTYPE XML interdite"):
        _adapt_hprim_xml(
            "<!DOCTYPE message [<!ENTITY internal 'value'>]><message>&internal;</message>",
            {},
        )


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
        payload='MSH|<?xml version="1.0"?><acte><ipp>$NIP$</ipp><dossier>$DOSSIER$</dossier><date>$DATE$</date><heure>$HEURE$</heure><emetteur>$EMETTEUR$</emetteur></acte>',
    ))
    endpoint = SystemEndpoint(name="Dépôt HPRIM", kind="HPRIM", role="sender", outbox_path=str(tmp_path), target_system_key="GAM-CIBLE")
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint])
    step = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).one()
    assert step.message_format == "xml"
    assert step.compiled_payload.startswith("<acte>")
    assert "$NIP$" not in step.compiled_payload and "$DOSSIER$" not in step.compiled_payload
    assert re.search(r"<date>\d{4}-\d{2}-\d{2}</date>", step.compiled_payload)
    assert re.search(r"<heure>\d{2}:\d{2}:\d{2}</heure>", step.compiled_payload)

    asyncio.run(execute_scenario_play(session, play.id))
    state = session.exec(select(ScenarioTargetState).where(ScenarioTargetState.scenario_id == scenario.id)).one()
    assert state.target_system_key == "GAM-CIBLE"
    assert state.status == "success"
    assert state.last_play_id == play.id


def test_real_play_uses_persistent_outbox_and_published_snapshot(session, tmp_path):
    scenario = _scenario(session)
    endpoint = SystemEndpoint(name="Dépôt durable", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint])
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()
    queued = session.exec(select(OutboundMessage).where(OutboundMessage.scenario_delivery_id.in_([item.id for item in deliveries]))).all()
    assert play.scenario_version_id is not None
    assert len(queued) == len(deliveries)
    assert all(item.outbox_id for item in deliveries)

    asyncio.run(execute_scenario_play(session, play.id))
    assert {item.status for item in session.exec(select(OutboundMessage).where(OutboundMessage.id.in_([item.id for item in queued]))).all()} == {"sent"}


def test_play_persists_assertion_verdict(session, tmp_path):
    scenario = _scenario(session)
    scenario.assertions_json = json.dumps([
        {"type": "minimum_success_steps", "value": 2},
        {"type": "payload_contains", "order_index": 1, "value": "ADT^A01"},
    ])
    session.add(scenario)
    endpoint = SystemEndpoint(name="Assertions", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint])
    play = asyncio.run(execute_scenario_play(session, play.id))
    evidence = json.loads(play.result_json)
    assert play.status == "success"
    assert evidence["qualification_verdict"] == "passed"
    assert len(evidence["assertions"]) == 2


def test_continue_other_targets_blocks_only_the_failed_target(session, tmp_path):
    scenario = InteropScenario(key="scenario-policy", name="Politique de reprise", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01", payload="MSH|^~\\&|A|B|C|D|202601010000||ADT^A01|1|P|2.5\rPID|||P"),
        InteropScenarioStep(scenario_id=scenario.id, order_index=2, message_format="hl7", message_type="ADT^A02", payload="MSH|^~\\&|A|B|C|D|202601010000||ADT^A02|2|P|2.5\rPID|||P"),
    ])
    failing = SystemEndpoint(name="MLLP indisponible", kind="MLLP", role="sender")
    receiving = SystemEndpoint(name="Dépôt disponible", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add_all([failing, receiving])
    session.commit()

    play = prepare_scenario_play(session, scenario, [failing, receiving], error_policy="continue_other_targets")
    play = asyncio.run(execute_scenario_play(session, play.id))
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()

    assert play.status == "scheduled"
    assert sorted(item.status for item in deliveries) == ["blocked", "retry", "sent", "sent"]


def test_step_routing_can_target_an_explicit_endpoint(session, tmp_path):
    scenario = InteropScenario(key="explicit-routing", name="Routage explicite", protocol="HL7")
    session.add(scenario)
    session.commit()
    first = SystemEndpoint(name="Cible A", kind="FILE", role="sender", outbox_path=str(tmp_path / "a"))
    second = SystemEndpoint(name="Cible B", kind="FILE", role="both", outbox_path=str(tmp_path / "b"))
    session.add_all([first, second])
    session.commit()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A28",
        payload="MSH|^~\\&|A|B|C|D|202601010000||ADT^A28|1|P|2.5^FRA^2.11\rPID|||P",
        route_mode="explicit", endpoint_ids_json=json.dumps([second.id]),
    ))
    session.commit()

    play = prepare_scenario_play(session, scenario, [first, second], dry_run=True)
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()

    assert [(item.endpoint_id, item.status) for item in deliveries] == [(first.id, "skipped"), (second.id, "pending")]


def test_step_delay_is_durable_and_reconciled_by_outbox(session, tmp_path):
    scenario = InteropScenario(key="durable-delay", name="Temporisation durable", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A28",
            payload="MSH|^~\\&|A|B|C|D|202601010000||ADT^A28|1|P|2.5^FRA^2.11\rPID|||P", delay_seconds=60,
        ),
        InteropScenarioStep(
            scenario_id=scenario.id, order_index=2, message_format="hl7", message_type="ADT^A31",
            payload="MSH|^~\\&|A|B|C|D|202601010001||ADT^A31|2|P|2.5^FRA^2.11\rPID|||P",
        ),
    ])
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint])
    play = asyncio.run(execute_scenario_play(session, play.id))
    deliveries = session.exec(
        select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id).order_by(ScenarioDelivery.id)
    ).all()
    assert play.status == "scheduled"
    assert [item.status for item in deliveries] == ["sent", "queued"]
    delayed = session.get(OutboundMessage, deliveries[1].outbox_id)
    delayed.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    session.add(delayed)
    session.commit()

    result = asyncio.run(process_due_messages(session))
    session.refresh(play)
    assert result["sent"] == 1
    assert play.status == "success"


def test_approved_positive_scenario_cannot_enqueue_invalid_output(session, tmp_path):
    scenario = InteropScenario(key="invalid-approved", name="Invalide approuvé", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A28",
        payload="MSH|^~\\&|A|B|C|D||||ADT^A28||P|\rPID|||P",
    ))
    session.add(ScenarioCatalogReview(scenario_id=scenario.id, status="approved"))
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    with pytest.raises(ScenarioPlayError, match="invalide avant émission"):
        prepare_scenario_play(session, scenario, [endpoint])
