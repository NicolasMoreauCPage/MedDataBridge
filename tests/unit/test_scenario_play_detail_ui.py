import json

from app.models_endpoints import SystemEndpoint
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlay, ScenarioPlayStep
from app.models_scenarios import InteropScenario


def test_scenario_play_detail_renders_the_responsive_delivery_workspace(client, session):
    scenario = InteropScenario(key="play-detail-ui", name="Suivi de jeu", protocol="HL7")
    endpoint = SystemEndpoint(name="Cible UI", kind="FILE", role="sender")
    session.add_all([scenario, endpoint])
    session.flush()
    play = ScenarioPlay(
        scenario_id=scenario.id,
        play_key="PLAY-UI-1",
        status="error",
        identity_json=json.dumps({
            "identifiers": {"ipp": "IPP-UI", "nda": "NDA-UI", "venue": "VEN-UI"},
            "practitioner": {"name": "Dr UI", "rpps": "123"},
        }),
    )
    session.add(play)
    session.flush()
    step = ScenarioPlayStep(
        play_id=play.id,
        order_index=1,
        name="Admission",
        message_format="hl7",
        source_payload="MSH|^~\\&|A|B|C|D|202609130000||ADT^A01|1|P|2.5",
        compiled_payload="MSH|^~\\&|A|B|C|D|202609130000||ADT^A01|1|P|2.5",
    )
    session.add(step)
    session.flush()
    session.add(ScenarioDelivery(
        play_id=play.id,
        play_step_id=step.id,
        endpoint_id=endpoint.id,
        status="error",
        transport="FILE",
        error_message="Destination indisponible",
        validation_status="valid",
    ))
    session.commit()

    response = client.get(f"/scenarios/{scenario.id}/plays/{play.id}")

    assert response.status_code == 200
    assert "PLAY-UI-1" in response.text
    assert "data-scenario-play-workspace" in response.text
    assert "js/scenario-play-workspace.js" in response.text
    assert response.text.count("Réessayer cette livraison") == 2
    assert "window.setTimeout(() => window.location.reload(), 5000)" not in response.text
