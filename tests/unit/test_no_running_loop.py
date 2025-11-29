import asyncio

from app.services.transport_inbound import _OnMessageInboundCallable


async def _dummy_async_handler(msg, session, endpoint=None):
    # mimic the real handler: return an HL7 ack string on success
    await asyncio.sleep(0)
    return "MSA|AA|1"


def test_on_message_inbound_sync_no_running_loop():
    wrapper = _OnMessageInboundCallable(_dummy_async_handler)

    # Call synchronously (no running event loop)
    result = wrapper("MSG", session=None, endpoint=None)

    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert "ack" in result
