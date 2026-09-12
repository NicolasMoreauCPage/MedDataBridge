import json

from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_practitioners import MedecinResponsable
from app.models_scenario_runs import ScenarioDelivery
from app.models_scenario_target_profiles import ScenarioTargetLocation, ScenarioTargetProfile
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import UniteFonctionnelle
from app.services.scenario_play_service import prepare_scenario_play


def _doctor(rpps: str, family: str) -> MedecinResponsable:
    return MedecinResponsable(rpps=rpps, adeli=rpps[-9:], family_name=family, given_name="Alice", prefix="Dr")


def test_delivery_payloads_use_the_uf_and_doctor_of_each_target_profile(session, tmp_path):
    doctor_a, doctor_b = _doctor("11111111111", "ALPHA"), _doctor("22222222222", "BETA")
    session.add_all([doctor_a, doctor_b])
    session.commit()
    uf_a = UniteFonctionnelle(identifier="UF-A", name="UF A", medecin_responsable_id=doctor_a.id)
    uf_b = UniteFonctionnelle(identifier="UF-B", name="UF B", medecin_responsable_id=doctor_b.id)
    session.add_all([uf_a, uf_b])
    session.commit()
    scenario = InteropScenario(key="target-clinical", name="Ciblage clinique", protocol="MIXED")
    session.add(scenario)
    session.commit()
    session.add_all([
        InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01", payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|OLD|P|2.5\rPID|||OLD\rPV1||I|||||999^OLD^DOC\rZBE|OLD||||||ANCIENNE-UF"),
        InteropScenarioStep(scenario_id=scenario.id, order_index=2, message_format="xml", message_type="HPRIM-CCAM", payload="<acte><ufResponsable>OLD-UF</ufResponsable><medecin><noRPPS>999</noRPPS><personne><nomUsuel>OLD</nomUsuel></personne></medecin></acte>"),
        InteropScenarioStep(scenario_id=scenario.id, order_index=3, message_format="fhir", message_type="Encounter", payload='{"resourceType":"Encounter"}'),
    ])
    profile_a, profile_b = ScenarioTargetProfile(target_system_key="CIBLE-A"), ScenarioTargetProfile(target_system_key="CIBLE-B")
    session.add_all([profile_a, profile_b])
    session.commit()
    session.add_all([
        ScenarioTargetLocation(profile_id=profile_a.id, role="hospitalisation", unite_fonctionnelle_id=uf_a.id, room="101", bed="A"),
        ScenarioTargetLocation(profile_id=profile_a.id, role="externe", unite_fonctionnelle_id=uf_a.id),
        ScenarioTargetLocation(profile_id=profile_b.id, role="hospitalisation", unite_fonctionnelle_id=uf_b.id, room="202", bed="B"),
        ScenarioTargetLocation(profile_id=profile_b.id, role="externe", unite_fonctionnelle_id=uf_b.id),
    ])
    endpoint_a = SystemEndpoint(name="A", kind="FILE", role="sender", target_system_key="CIBLE-A", outbox_path=str(tmp_path / "a"))
    endpoint_b = SystemEndpoint(name="B", kind="FILE", role="sender", target_system_key="CIBLE-B", outbox_path=str(tmp_path / "b"))
    session.add_all([endpoint_a, endpoint_b])
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint_a, endpoint_b], dry_run=True)
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()
    by_target = {delivery.endpoint_id: delivery for delivery in deliveries if delivery.play_step_id and delivery.compiled_payload and "ADT^A01" in delivery.compiled_payload}
    assert "UF-A^101^A" in by_target[endpoint_a.id].compiled_payload
    assert "11111111111^ALPHA^Alice" in by_target[endpoint_a.id].compiled_payload
    zbe_a = by_target[endpoint_a.id].compiled_payload.split("ZBE|")[1].split("\r", 1)[0].split("|")
    assert zbe_a[0].isdigit() and "UF-A" in by_target[endpoint_a.id].compiled_payload.split("ZBE|")[1]
    assert "UF-B^202^B" in by_target[endpoint_b.id].compiled_payload
    assert "22222222222^BETA^Alice" in by_target[endpoint_b.id].compiled_payload
    assert "UF-B" in by_target[endpoint_b.id].compiled_payload.split("ZBE|")[1]
    assert by_target[endpoint_a.id].compiled_payload != by_target[endpoint_b.id].compiled_payload

    hprim_a = next(item for item in deliveries if item.endpoint_id == endpoint_a.id and "<acte" in (item.compiled_payload or ""))
    hprim_b = next(item for item in deliveries if item.endpoint_id == endpoint_b.id and "<acte" in (item.compiled_payload or ""))
    assert "<ufResponsable>UF-A</ufResponsable>" in hprim_a.compiled_payload
    assert "11111111111" in hprim_a.compiled_payload
    assert "<ufResponsable>UF-B</ufResponsable>" in hprim_b.compiled_payload
    assert "22222222222" in hprim_b.compiled_payload
    assert json.loads(hprim_a.target_context_json)["source"] == "target_profile"

    fhir_a = next(item for item in deliveries if item.endpoint_id == endpoint_a.id and '"resourceType": "Encounter"' in (item.compiled_payload or ""))
    fhir_b = next(item for item in deliveries if item.endpoint_id == endpoint_b.id and '"resourceType": "Encounter"' in (item.compiled_payload or ""))
    assert json.loads(fhir_a.compiled_payload)["location"][0]["location"]["display"] == "UF-A"
    assert json.loads(fhir_a.compiled_payload)["participant"][0]["individual"]["identifier"]["value"] == "11111111111"
    assert json.loads(fhir_b.compiled_payload)["location"][0]["location"]["display"] == "UF-B"
    assert json.loads(fhir_b.compiled_payload)["participant"][0]["individual"]["identifier"]["value"] == "22222222222"


def test_unconfigured_target_uses_an_active_uf_and_its_responsible_doctor(session, tmp_path):
    doctor = _doctor("33333333333", "LOCAL")
    session.add(doctor)
    session.commit()
    uf = UniteFonctionnelle(identifier="UF-LOCAL-PAIRED", name="UF locale", medecin_responsable_id=doctor.id)
    session.add(uf)
    scenario = InteropScenario(key="target-fallback", name="Repli structure", protocol="HL7")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01", payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|OLD|P|2.5\rPID|||OLD\rPV1||I|||||OLD^DOCTOR"))
    endpoint = SystemEndpoint(name="Sans profil", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()

    play = prepare_scenario_play(session, scenario, [endpoint], dry_run=True)
    delivery = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).one()
    context = json.loads(delivery.target_context_json)
    assert context["source"] == "structure_fallback"
    assert context["location"]["code"] == "UF-LOCAL-PAIRED"
    assert "UF-LOCAL-PAIRED" in delivery.compiled_payload
    assert "33333333333^LOCAL^Alice" in delivery.compiled_payload
