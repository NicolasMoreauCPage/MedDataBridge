"""Contrats d'import des scénarios historiques concaténés."""

from sqlmodel import select

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_import import split_embedded_messages, split_embedded_messages_in_scenario


PAYLOAD = """MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A28|ONE|P|2.5
PID|||IPP
MSH|^~\\&|SRC|FAC|DST|FAC|202601010001||ADT^A01|TWO|P|2.5
PID|||IPP
MSH|<?xml version="1.0"?><evenementsServeurActes version="1.06"/>"""


def test_split_embedded_messages_returns_one_step_per_hl7_or_hprim_message():
    messages = split_embedded_messages(PAYLOAD, "hprimxml")

    assert [(item["message_format"], item["message_type"]) for item in messages] == [
        ("hl7", "ADT^A28"), ("hl7", "ADT^A01"), ("xml", "HPRIM"),
    ]
    assert messages[-1]["payload"].startswith("<?xml")


def test_existing_scenario_can_be_normalized_without_losing_message_order(session):
    scenario = InteropScenario(key="embedded-messages", name="Export historique", protocol="MIXED")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id, order_index=1, name="Export", message_format="hprimxml", payload=PAYLOAD,
    ))
    session.commit()

    added = split_embedded_messages_in_scenario(session, scenario)
    steps = session.exec(
        select(InteropScenarioStep)
        .where(InteropScenarioStep.scenario_id == scenario.id)
        .order_by(InteropScenarioStep.order_index)
    ).all()

    assert added == 2
    assert [(step.order_index, step.message_format, step.message_type) for step in steps] == [
        (1, "hl7", "ADT^A28"), (2, "hl7", "ADT^A01"), (3, "xml", "HPRIM"),
    ]
