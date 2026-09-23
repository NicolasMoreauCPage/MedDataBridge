from types import SimpleNamespace

from app.models_endpoints import MessageLog, SystemEndpoint
from app.services.pam_emission import (
    dump_outbound_pam_payload,
    send_outbound_pam,
    upsert_outbound_pam_log,
    validate_outbound_pam,
)


def test_outbound_pam_payload_dump_is_atomic_and_skips_generated_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDBRIDGE_OUT_DIR", str(tmp_path))

    dump_outbound_pam_payload("MSH|^~\\&|SOURCE", 42)
    dumped = list((tmp_path / "pam").glob("mllp_42_*.hl7"))

    assert len(dumped) == 1
    assert dumped[0].read_text(encoding="utf-8") == "MSH|^~\\&|SOURCE"
    dump_outbound_pam_payload("[Emission error: missing]", 42)
    assert len(list((tmp_path / "pam").glob("*.hl7"))) == 1


def test_outbound_pam_log_is_upserted_by_correlation(session):
    endpoint = SystemEndpoint(name="PAM log test", kind="MLLP", role="sender")
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)

    first = upsert_outbound_pam_log(session, endpoint_id=endpoint.id, correlation_id="CTRL-1", payload="first", acknowledgment="AA", status="sent", validation_status="ok", validation_issues="[]")
    second = upsert_outbound_pam_log(session, endpoint_id=endpoint.id, correlation_id="CTRL-1", payload="second", acknowledgment="AA", status="sent", validation_status="ok", validation_issues="[]")

    assert first.id == second.id
    assert session.get(MessageLog, first.id).payload == "second"


def test_outbound_pam_transport_interprets_positive_and_negative_acknowledgments():
    positive = "MSH|^~\\&|DST|DST|SRC|SRC|20260923||ACK|A1|P|2.5\rMSA|AA|CTRL"
    negative = "MSH|^~\\&|DST|DST|SRC|SRC|20260923||ACK|A2|P|2.5\rMSA|AE|CTRL"

    assert send_outbound_pam("localhost", 2575, "payload", sender=lambda *_: positive) == ("sent", positive)
    assert send_outbound_pam("localhost", 2575, "payload", sender=lambda *_: negative) == ("error", negative)


def test_outbound_pam_transport_marks_ack_without_msa_as_an_error():
    status, acknowledgment = send_outbound_pam(
        "localhost", 2575, "payload", sender=lambda *_: "MSH|^~\\&|ACK"
    )

    assert status == "error"
    assert acknowledgment == "[ACK MLLP sans segment MSA]"


def test_outbound_pam_validation_keeps_first_functional_error():
    result = SimpleNamespace(
        level="fail",
        issues=[
            SimpleNamespace(severity="warn", message="Avertissement"),
            SimpleNamespace(severity="error", message="Champ PID-3 absent"),
        ],
    )

    outcome = validate_outbound_pam("payload", validator=lambda *_args, **_kwargs: result)

    assert outcome.status == "fail"
    assert outcome.first_error == "Champ PID-3 absent"
    assert "PID-3" in outcome.issues


def test_outbound_pam_validation_degrades_to_warning_when_validator_fails():
    outcome = validate_outbound_pam(
        "payload", validator=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError())
    )

    assert outcome.status == "warn"
    assert "VALIDATOR_ERROR" in outcome.issues
