from types import SimpleNamespace

from sqlmodel import select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.services.file_endpoint_emission import emit_file_endpoint


def _pam_payload(*args, **kwargs):
    return "MSH|^~\\&|SRC|FAC|DST|FAC|20260923||ADT^A28|CTRL|P|2.5\rPID|1||IPP-1"


def _fhir_payload(*args, **kwargs):
    return {"resourceType": "Bundle", "type": "transaction", "entry": []}


def test_file_endpoint_writes_atomically_and_persists_log(session, tmp_path):
    endpoint = SystemEndpoint(name="FILE test", kind="FILE", role="sender", outbox_path=str(tmp_path))
    session.add(endpoint)
    session.commit()
    entity = SimpleNamespace(id=7, correlation_id="corr-file")

    emit_file_endpoint(
        session,
        endpoint=endpoint,
        entity=entity,
        entity_type="patient",
        operation="insert",
        generate_pam=_pam_payload,
        generate_fhir=_fhir_payload,
    )

    files = list((tmp_path / "pam").glob("patient_7_*.hl7"))
    assert len(files) == 1
    assert not list((tmp_path / "pam").glob("*.tmp"))
    log = session.exec(select(MessageLog).where(MessageLog.endpoint_id == endpoint.id)).one()
    assert log.kind == "FILE"
    assert log.status == "sent"
    assert log.ack_payload == f"WROTE:{files[0]}"


def test_sftp_endpoint_disconnects_and_persists_log(session, monkeypatch):
    endpoint = SystemEndpoint(
        name="SFTP test",
        kind="SFTP",
        role="sender",
        ftp_host="sftp.example.test",
        ftp_remote_outbox_path="/out",
    )
    session.add(endpoint)
    session.commit()
    entity = SimpleNamespace(id=8, correlation_id="corr-sftp")
    calls = []

    class FakeWriter:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def connect(self):
            calls.append(("connect",))

        def write_file(self, filename, payload):
            calls.append(("write", filename, payload))

        def disconnect(self):
            calls.append(("disconnect",))

    monkeypatch.setattr("app.adapters.sftp_writer.SFTPWriter", FakeWriter)
    emit_file_endpoint(
        session,
        endpoint=endpoint,
        entity=entity,
        entity_type="patient",
        operation="insert",
        generate_pam=_pam_payload,
        generate_fhir=_fhir_payload,
    )

    assert [call[0] for call in calls] == ["init", "connect", "write", "disconnect"]
    log = session.exec(select(MessageLog).where(MessageLog.endpoint_id == endpoint.id)).one()
    assert log.kind == "SFTP"
    assert log.status == "sent"
    assert log.ack_payload.startswith("SENT_SFTP:patient_8_")
