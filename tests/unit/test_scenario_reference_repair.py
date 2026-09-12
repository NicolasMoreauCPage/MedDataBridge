from app.models_scenarios import InteropScenarioStep
from app.services.scenario_reference_repair import _trigger, reference_prerequisite_payloads, zbe1, zbe_action


def _step(trigger: str, action: str, original: str, movement_id: str = "MVT-SOURCE") -> InteropScenarioStep:
    return InteropScenarioStep(
        id=42, scenario_id=1, order_index=3, message_format="hl7", message_type=f"ADT^{trigger}",
        payload=(
            f"MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^{trigger}|1|P|2.5\r"
            f"PID|||P\rZBE|{movement_id}|||{action}||{original}"
        ),
    )


def test_z99_prerequisite_keeps_exact_zbe1_reference():
    prerequisites = reference_prerequisite_payloads(_step("Z99", "UPDATE", "A01", "ZBE-77"))

    assert [trigger for trigger, _ in prerequisites] == ["A01"]
    assert _trigger(prerequisites[0][1]) == "A01"
    assert zbe1(prerequisites[0][1]) == "ZBE-77"
    assert zbe_action(prerequisites[0][1]) == "INSERT"


def test_cancel_prerequisite_builds_valid_path_to_original_movement():
    prerequisites = reference_prerequisite_payloads(_step("A12", "CANCEL", "A02", "ZBE-88"))

    assert [trigger for trigger, _ in prerequisites] == ["A01", "A02"]
    assert zbe1(prerequisites[0][1]).startswith("PREREQ-42-")
    assert zbe1(prerequisites[-1][1]) == "ZBE-88"
    assert zbe_action(prerequisites[-1][1]) == "INSERT"
