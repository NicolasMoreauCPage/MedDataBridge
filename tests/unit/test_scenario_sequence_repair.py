from app.models_scenarios import InteropScenarioStep
from app.services.scenario_sequence_repair import repaired_step_order


def _step(order: int, trigger: str) -> InteropScenarioStep:
    return InteropScenarioStep(
        scenario_id=1,
        order_index=order,
        message_format="hl7",
        payload=f"MSH|^~\\&|SRC|FAC|DST|FAC|202609120900||ADT^{trigger}|{order}|P|2.5\rPID|1||P-1^^^SRC^PI",
    )


def test_reorders_a_discharge_before_its_admission():
    repaired = repaired_step_order([_step(1, "A03"), _step(2, "A01")])
    assert repaired is not None
    assert [step.order_index for step in repaired] == [2, 1]


def test_does_not_repair_a_multi_patient_scenario_automatically():
    first, second = _step(1, "A03"), _step(2, "A01")
    second.payload = second.payload.replace("P-1", "P-2")
    assert repaired_step_order([first, second]) is None
