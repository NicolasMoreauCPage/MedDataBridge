import pytest

from app.services.scheduler import BackgroundScheduler, POLLABLE_FILE_ENDPOINT_KINDS


@pytest.mark.asyncio
async def test_scheduler_processes_due_outbox_messages(monkeypatch):
    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    called = {}

    async def fake_process(session, limit):
        called["session"] = session
        called["limit"] = limit
        return {"processed": 2, "sent": 1, "retry": 1, "failed": 0}

    monkeypatch.setattr("app.services.scheduler.session_factory", lambda: DummySession())
    monkeypatch.setattr("app.services.scheduler.process_due_messages", fake_process)

    await BackgroundScheduler()._process_due_outbox()

    assert isinstance(called["session"], DummySession)
    assert called["limit"] == 100


def test_scheduler_polls_local_file_and_sftp_endpoints():
    assert POLLABLE_FILE_ENDPOINT_KINDS == ("FILE", "SFTP")
