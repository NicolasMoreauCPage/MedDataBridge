from app.services.scenario_validation import validate_scenario


def test_identity_message_does_not_break_following_initial_movement_with_literal_cr():
    messages = (
        r"MSH|^~\&|SRC|FAC|DST|FAC|202601010000||ADT^A28|1|P|2.5\rEVN|A28\rPID|||P1\r"
        r"MSH|^~\&|SRC|FAC|DST|FAC|202601010001||ADT^A01|2|P|2.5\rEVN|A01\rPID|||P1\rPV1||I"
    )

    result = validate_scenario(messages)

    assert not [issue for issue in result.workflow_issues if issue.code.startswith("WORKFLOW_INVALID")]


def test_workflow_is_tracked_per_patient_in_a_multi_patient_scenario():
    messages = "\n".join([
        "MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|1|P|2.5\rEVN|A01\rPID|||MOTHER\rPV1||I",
        "MSH|^~\\&|SRC|FAC|DST|FAC|202601010001||ADT^A01|2|P|2.5\rEVN|A01\rPID|||BABY\rPV1||I",
    ])

    result = validate_scenario(messages)

    assert not [issue for issue in result.workflow_issues if issue.code.startswith("WORKFLOW_INVALID")]
    assert any(issue.code == "SCENARIO_MULTIPLE_PATIENTS" and issue.severity == "warn" for issue in result.coherence_issues)
