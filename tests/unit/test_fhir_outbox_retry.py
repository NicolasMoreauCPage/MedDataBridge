"""Régressions des reprises FHIR durables depuis l'émetteur historique."""

from sqlmodel import select

from app.models import Patient
from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.emit_on_create import emit_to_senders_async


def test_failed_fhir_emission_is_queued_without_blocking_retry_sleep(session, monkeypatch):
    endpoint = SystemEndpoint(
        name="FHIR indisponible",
        kind="FHIR",
        role="sender",
        is_enabled=True,
        base_url="http://fhir.example.test/api",
    )
    patient = Patient(identifier="IPP-FHIR-RETRY", family="Durand", given="Camille")
    session.add_all([endpoint, patient])
    session.commit()
    calls = []

    async def rejected_fhir_target(base_url, _bundle, auth_kind="none", auth_token=None):
        calls.append((base_url, auth_kind, auth_token))
        return 503, {"issue": "temporarily unavailable"}

    monkeypatch.setattr(
        "app.services.fhir_transport.post_fhir_bundle", rejected_fhir_target
    )

    emit_to_senders_async(patient, "patient", session)

    assert calls == [("http://fhir.example.test/api", "none", None)]
    log = session.exec(
        select(MessageLog).where(MessageLog.endpoint_id == endpoint.id)
    ).one()
    queued = session.exec(
        select(OutboundMessage).where(OutboundMessage.source_message_log_id == log.id)
    ).one()
    assert log.status == "error"
    assert queued.protocol == "FHIR"
    assert queued.status == "pending"
    assert queued.payload == log.payload


def test_failed_mllp_emission_is_queued_after_one_attempt(session, monkeypatch):
    endpoint = SystemEndpoint(
        name="MLLP indisponible",
        kind="MLLP",
        role="sender",
        is_enabled=True,
        host="mllp.example.test",
        port=2575,
    )
    patient = Patient(identifier="IPP-MLLP-RETRY", family="Martin", given="Lou")
    session.add_all([endpoint, patient])
    session.commit()
    calls = []

    async def rejected_mllp(host, port, payload):
        calls.append((host, port, payload))
        return "MSH|^~\\&|R|F|S|F|20260101||ACK^A01|ACK1|P|2.5\\rMSA|AE|MSG1"

    monkeypatch.setattr("app.services.mllp.send_mllp", rejected_mllp)

    emit_to_senders_async(patient, "patient", session)

    assert len(calls) == 1
    log = session.exec(
        select(MessageLog).where(MessageLog.endpoint_id == endpoint.id)
    ).one()
    queued = session.exec(
        select(OutboundMessage).where(OutboundMessage.source_message_log_id == log.id)
    ).one()
    assert log.status == "error"
    assert queued.protocol == "MLLP"
    assert queued.status == "pending"
    assert queued.payload == log.payload
