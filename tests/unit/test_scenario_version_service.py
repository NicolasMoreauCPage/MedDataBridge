from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_version_service import snapshot_scenario_version


def test_published_version_is_immutable_and_archives_previous(session):
    scenario = InteropScenario(key="versioned-scenario", name="Versionné")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", payload="MSH|ONE"))
    session.commit()

    first = snapshot_scenario_version(session, scenario, publish=True)
    session.commit()
    scenario.steps[0].payload = "MSH|TWO"
    session.add(scenario.steps[0])
    second = snapshot_scenario_version(session, scenario, comment="Message corrigé", publish=True)
    session.commit()

    assert (first.version_number, first.status) == (1, "archived")
    assert (second.version_number, second.status) == (2, "published")
    assert scenario.current_version_id == second.id
    assert "MSH|ONE" in first.content_json
    assert "MSH|TWO" in second.content_json
