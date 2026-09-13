import json

from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_scenarios import InteropScenario, InteropScenarioStep


def test_scenario_editor_exposes_only_sender_endpoints_and_persists_routing(client, session, tmp_path):
    scenario = InteropScenario(key="routing-ui", name="Routage IHM", protocol="HL7")
    sender = SystemEndpoint(name="Émetteur", kind="FILE", role="sender", outbox_path=str(tmp_path / "a"))
    both = SystemEndpoint(name="Bidirectionnel", kind="FILE", role="both", outbox_path=str(tmp_path / "b"))
    receiver = SystemEndpoint(name="Récepteur seul", kind="FILE", role="receiver", outbox_path=str(tmp_path / "c"))
    session.add_all([scenario, sender, both, receiver])
    session.commit()

    page = client.get(f"/scenarios/{scenario.id}")

    assert page.status_code == 200
    assert "Émetteur" in page.text
    assert "Bidirectionnel" in page.text
    assert "Récepteur seul" not in page.text

    response = client.post(
        f"/scenarios/{scenario.id}/steps",
        data={
            "name": "Identité",
            "message_format": "hl7",
            "message_type": "ADT^A28",
            "payload": "MSH|^~\\&|A|B|C|D|202601010000||ADT^A28|1|P|2.5^FRA^2.11\rPID|||P",
            "is_required": "true",
            "route_mode": "explicit",
            "route_endpoint_ids": str(both.id),
            "target_system_key": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    step = session.exec(select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == scenario.id)).one()
    assert step.order_index == 1
    assert step.is_required is True
    assert step.route_mode == "explicit"
    assert json.loads(step.endpoint_ids_json) == [both.id]
    exported = client.get(f"/scenarios/{scenario.id}/export").json()
    assert exported["steps"][0]["is_required"] is True
    assert exported["steps"][0]["route_mode"] == "explicit"
    assert exported["steps"][0]["endpoint_ids"] == [both.id]
