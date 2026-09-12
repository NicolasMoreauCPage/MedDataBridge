import pytest

from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.services.qualification_engine import _expected_outcome, evaluate_expected_outcome


def _log(*, order=1, status="error", ack="AR", error="Transition PAM interdite"):
    return ScenarioExecutionStepLog(order_index=order, status=status, ack_code=ack, error_message=error)


def test_negative_scenario_passes_when_expected_rejection_is_observed():
    results = evaluate_expected_outcome(
        ScenarioExecutionRun(status="error"),
        [_log(order=2)],
        {"mode": "negative", "ack_codes": ["AE", "AR"], "step_order": 2, "error_contains": "PAM"},
    )
    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].actual["rejected"] is True


def test_negative_scenario_fails_when_rejection_code_is_not_the_expected_one():
    results = evaluate_expected_outcome(
        ScenarioExecutionRun(status="error"), [_log()], {"mode": "negative", "ack_codes": ["AE"]}
    )
    assert results[0].passed is False


def test_positive_contract_accepts_successful_transport():
    results = evaluate_expected_outcome(
        ScenarioExecutionRun(status="success"), [_log(status="sent", ack="AA", error="")],
        {"mode": "positive", "ack_codes": ["AA"]},
    )
    assert results[0].passed is True


@pytest.mark.parametrize("payload", ["[]", '{"mode":"unexpected"}', '{"ack_codes":"AA"}'])
def test_expected_outcome_rejects_invalid_contract(payload):
    with pytest.raises(ValueError):
        _expected_outcome(payload)
