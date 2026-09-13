"""Tests de la reprise persistante des émissions sortantes."""

import pytest
from sqlmodel import select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.outbox_service import (
    _delivery_ack_code,
    enqueue_failed_message_logs,
    outbox_stats,
    process_due_messages,
    retry_now,
)


def test_delivery_ack_code_is_a_short_protocol_verdict():
    ack = "MSH|^~\\&|R|F|S|F|20260101||ACK^A01|ACK1|P|2.5\rMSA|AA|MSG1\r"

    assert _delivery_ack_code("MLLP", ack) == "AA"
    assert _delivery_ack_code("FHIR", "{}", 201) == "201"
    assert _delivery_ack_code("FILE", "FILE:test.hl7") == "OK"


def test_outbox_stats_exposes_backlog_and_terminal_failures(session):
    endpoint = SystemEndpoint(name="Stats", kind="FILE", role="sender", outbox_path="/tmp")
    session.add(endpoint)
    session.commit()
    session.add_all([
        OutboundMessage(endpoint_id=endpoint.id, protocol="FILE", payload="one", status="pending"),
        OutboundMessage(endpoint_id=endpoint.id, protocol="FILE", payload="two", status="failed"),
    ])
    session.commit()

    stats = outbox_stats(session)

    assert stats["status"] == "degraded"
    assert stats["counts"]["pending"] == 1
    assert stats["counts"]["failed"] == 1
    assert stats["due"] == 1


@pytest.mark.asyncio
async def test_failed_log_is_persisted_then_marked_retry(session):
    endpoint = SystemEndpoint(name="MLLP indisponible", kind="MLLP", role="sender", host="127.0.0.1", port=1)
    session.add(endpoint)
    session.commit()
    log = MessageLog(
        direction="out", kind="MLLP", endpoint_id=endpoint.id,
        message_type="MFN^M05", payload="MSH|^~\\&|||||||MFN^M05|1|P|2.5", status="error",
    )
    session.add(log)
    session.commit()

    assert enqueue_failed_message_logs(session) == 1
    session.commit()
    row = session.exec(select(OutboundMessage)).one()
    assert row.status == "pending"
    assert enqueue_failed_message_logs(session) == 0  # pas de doublon au redémarrage

    result = await process_due_messages(session)
    session.refresh(row)
    assert result == {"processed": 1, "sent": 0, "retry": 1, "failed": 0}
    assert row.status == "retry"
    assert row.attempts == 1
    assert row.last_error

    retry_now(session, row.id)
    session.commit()
    session.refresh(row)
    assert row.status == "pending"
    assert row.attempts == 0


@pytest.mark.asyncio
async def test_failed_outbox_is_not_requeued_by_the_scheduler(session):
    endpoint = SystemEndpoint(name="MLLP indisponible", kind="MLLP", role="sender", host="127.0.0.1", port=1)
    session.add(endpoint)
    session.commit()
    source_log = MessageLog(
        direction="out", kind="MLLP", endpoint_id=endpoint.id,
        message_type="MFN^M05", payload="MSH|^~\\&|||||||MFN^M05|1|P|2.5", status="pending",
    )
    session.add(source_log)
    session.commit()

    assert enqueue_failed_message_logs(session) == 1
    session.commit()
    row = session.exec(select(OutboundMessage)).one()
    row.max_attempts = 1
    session.add(row)
    session.commit()

    result = await process_due_messages(session)
    session.refresh(row)
    session.refresh(source_log)

    assert result == {"processed": 1, "sent": 0, "retry": 0, "failed": 1}
    assert row.status == "failed"
    assert source_log.status == "error"
    assert source_log.ack_payload == row.response_payload
    assert enqueue_failed_message_logs(session) == 0
