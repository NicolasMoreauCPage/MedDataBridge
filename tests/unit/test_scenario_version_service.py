import json

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_qualification_service import publication_issues
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


def test_published_snapshot_versions_expected_outcome(session):
    scenario = InteropScenario(
        key="negative-outcome",
        name="Rejet attendu",
        expected_outcome_json='{"mode":"negative","ack_codes":["AR"]}',
    )
    session.add(scenario)
    session.commit()

    version = snapshot_scenario_version(session, scenario, publish=True)
    content = json.loads(version.content_json)

    assert content["expected_outcome_json"] == scenario.expected_outcome_json


def test_publication_requires_portable_qualification_contract(session):
    scenario = InteropScenario(key="publication-check", name="Publication")
    session.add(scenario)
    session.commit()
    session.add(
        InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=1,
            message_format="hl7",
            payload="MSH|ONE",
        )
    )
    session.commit()

    assert len(publication_issues(scenario)) == 4

    scenario.functional_comment = "Vérifie le rejet d'une admission invalide."
    scenario.preconditions_json = '[{"type":"endpoint_kind","equals":"MLLP"}]'
    scenario.assertions_json = '[{"type":"ack_code","order_index":1,"equals":"AR"}]'
    scenario.expected_outcome_json = '{"mode":"negative","ack_codes":["AR"]}'

    assert publication_issues(scenario) == []
