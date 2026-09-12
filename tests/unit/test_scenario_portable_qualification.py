from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import GHTContext
from app.services.scenario_import import import_scenario_from_json


def test_scenario_import_preserves_qualification_contract(session):
    ght_context = GHTContext(name="GHT portable", code="PORTABLE")
    session.add(ght_context); session.commit()
    payload = {
        "key": "portable-negative", "name": "Test négatif portable", "protocol": "HL7",
        "functional_comment": "Vérifie le rejet d'une transition invalide.",
        "preconditions_json": '[{"type":"minimum_steps","value":1}]',
        "assertions_json": '[]',
        "expected_outcome_json": '{"mode":"negative","ack_codes":["AR"]}',
        "steps": [{"order_index": 1, "name": "Rejet", "description": "Transition invalide", "message_type": "ADT^A03", "format": "hl7", "payload": "MSH|^~\\&|S|F|R|F|||ADT^A03", "assertions_json": '[]'}],
    }
    scenario = import_scenario_from_json(session, payload, ght_context.id)
    step = session.get(InteropScenarioStep, scenario.steps[0].id)

    assert scenario.expected_outcome_json == payload["expected_outcome_json"]
    assert scenario.functional_comment == payload["functional_comment"]
    assert (step.name, step.description, step.assertions_json) == ("Rejet", "Transition invalide", "[]")
