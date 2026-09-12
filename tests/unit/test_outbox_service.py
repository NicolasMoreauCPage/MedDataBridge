"""Tests de la reprise persistante des émissions sortantes."""

import pytest
from sqlmodel import select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.outbox_service import (
    enqueue_failed_message_logs,
    process_due_messages,
    retry_now,
)


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
