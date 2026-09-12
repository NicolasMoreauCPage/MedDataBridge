import pytest
from sqlmodel import select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.outbox_service import process_outbox_message
from app.services.scenario_play_service import _transport_for


@pytest.mark.asyncio
async def test_sftp_outbox_delivery_uses_the_persistent_payload(session, monkeypatch):
    endpoint = SystemEndpoint(name="SFTP", kind="SFTP", role="sender", ftp_host="example.test", ftp_remote_outbox_path="/out")
    session.add(endpoint)
    session.commit()
    row = OutboundMessage(endpoint_id=endpoint.id, protocol="SFTP", message_type="HPRIM", payload="<xml/>")
    session.add(row)
    session.commit()
    calls = []
    monkeypatch.setattr("app.services.outbox_service._send_sftp", lambda ep, filename, payload: calls.append((ep.id, filename, payload)))

    processed = await process_outbox_message(session, row.id)

    assert processed.status == "sent"
    assert calls == [(endpoint.id, f"outbox_{row.id}.xml", "<xml/>")]
    log = session.exec(select(MessageLog).where(MessageLog.endpoint_id == endpoint.id)).one()
    assert log.kind == "HPRIM"


def test_scenario_routes_supported_payloads_to_ftp_and_sftp():
    assert _transport_for(SystemEndpoint(name="FTP", kind="FTP"), "xml") == "FTP"
    assert _transport_for(SystemEndpoint(name="SFTP", kind="SFTP"), "hl7") == "SFTP"
