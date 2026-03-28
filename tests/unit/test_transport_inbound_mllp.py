import asyncio
from datetime import datetime, timezone

from sqlmodel import select

from app.models_shared import MessageLog
from app.services.mllp import (
    _hexdump,
    build_ack,
    deframe_hl7,
    frame_hl7,
    parse_msh_fields,
    send_mllp,
    start_mllp_server,
    stop_mllp_server,
)
from app.services.transport_inbound import _validate_message_structure, on_message_inbound


def _base_msh(msg_type: str, control_id: str = "CTRL1") -> str:
    return f"MSH|^~\\&|SRC_APP|SRC_FAC|DST_APP|DST_FAC|20260328090000||{msg_type}|{control_id}|P|2.5\r"


def _seed_patient_graph_with_mouvement(session, identifier: str = "12345", trigger_event: str = "A01"):
    from app.db import get_next_sequence
    from app.models import Dossier, Mouvement, Patient, Venue

    patient = Patient(identifier=identifier, family="DOE", given="JOHN", gender="male")
    session.add(patient)
    session.flush()

    dossier = Dossier(
        dossier_seq=get_next_sequence(session, "dossier"),
        patient_id=patient.id,
        admit_time=datetime.now(),
    )
    session.add(dossier)
    session.flush()

    venue = Venue(
        venue_seq=get_next_sequence(session, "venue"),
        dossier_id=dossier.id,
        start_time=datetime.now(),
        code="WARD",
        label="Ward Test",
    )
    session.add(venue)
    session.flush()

    mouvement = Mouvement(
        mouvement_seq=get_next_sequence(session, "mouvement"),
        venue_id=venue.id,
        type=f"ADT^{trigger_event}",
        when=datetime.now(),
        location="WARD-A",
        movement_type="admission",
        trigger_event=trigger_event,
        status="active",
    )
    session.add(mouvement)
    session.commit()
    session.refresh(mouvement)
    return mouvement


def _seed_patient_graph(session, identifier: str = "12345", trigger_event: str = "A01"):
    from app.db import get_next_sequence
    from app.models import Dossier, Mouvement, Patient, Venue

    patient = Patient(identifier=identifier, family="DOE", given="JOHN", gender="male")
    session.add(patient)
    session.flush()

    dossier = Dossier(
        dossier_seq=get_next_sequence(session, "dossier"),
        patient_id=patient.id,
        admit_time=datetime.now(),
    )
    session.add(dossier)
    session.flush()

    venue = Venue(
        venue_seq=get_next_sequence(session, "venue"),
        dossier_id=dossier.id,
        start_time=datetime.now(),
        code="WARD-LOOKUP",
        label="Ward Lookup",
    )
    session.add(venue)
    session.flush()

    mouvement = Mouvement(
        mouvement_seq=get_next_sequence(session, "mouvement"),
        venue_id=venue.id,
        type=f"ADT^{trigger_event}",
        when=datetime.now(),
        location="WARD-B",
        movement_type="admission",
        trigger_event=trigger_event,
        status="active",
    )
    session.add(mouvement)
    session.commit()

    return {
        "patient": patient,
        "dossier": dossier,
        "venue": venue,
        "mouvement": mouvement,
    }


def test_deframe_hl7_extracts_multiple_messages():
    m1 = "MSH|^~\\&|A|B|C|D|20260328090000||ADT^A01|C1|P|2.5\rPID|1"
    m2 = "MSH|^~\\&|A|B|C|D|20260328090001||ADT^A03|C2|P|2.5\rPID|1"

    stream = b"NOISE" + frame_hl7(m1) + b"JUNK" + frame_hl7(m2)
    frames = deframe_hl7(stream)

    assert len(frames) == 2
    assert "ADT^A01" in frames[0]
    assert "ADT^A03" in frames[1]


def test_deframe_hl7_no_frame_returns_empty_list():
    assert deframe_hl7(b"NO_FRAME_DATA") == []


def test_parse_msh_fields_extracts_core_values():
    message = _base_msh("ADT^A01", "CTRL99") + "PID|1"
    msh = parse_msh_fields(message)

    assert msh["sending_app"] == "SRC_APP"
    assert msh["sending_facility"] == "SRC_FAC"
    assert msh["msg_type"] == "ADT^A01"
    assert msh["type"] == "ADT"
    assert msh["trigger"] == "A01"
    assert msh["control_id"] == "CTRL99"


def test_build_ack_with_error_includes_err_segment():
    original = _base_msh("ADT^A01", "CTRL_ERR") + "PID|1"
    ack = build_ack(original, ack_code="AE", text="Validation failed")

    assert ack.startswith("MSH|")
    assert "MSA|AE|CTRL_ERR|Validation failed" in ack
    assert "ERR|||207^Validation failed^HL70357|E" in ack


def test_hexdump_renders_offsets_and_text():
    dump = _hexdump(b"ABC\x00DEF")
    assert "0000" in dump
    assert "41 42 43" in dump
    assert "ABC.DEF" in dump


def test_send_mllp_uses_connection_and_returns_first_frame(monkeypatch):
    class FakeReader:
        async def read(self, _size):
            return frame_hl7("MSH|^~\\&|ACK|ACK|SRC|SRC|20260328090000||ACK^A01|A1|P|2.5\rMSA|AA|CTRL")

    class FakeWriter:
        def __init__(self):
            self.written = b""
            self.closed = False

        def write(self, data):
            self.written += data

        async def drain(self):
            return None

        def close(self):
            self.closed = True

        async def wait_closed(self):
            return None

    writer = FakeWriter()

    async def _fake_open_connection(_host, _port):
        return FakeReader(), writer

    monkeypatch.setattr("asyncio.open_connection", _fake_open_connection)
    ack = asyncio.run(
        send_mllp(
            "localhost",
            2575,
            "MSH|^~\\&|SRC|SRC|DST|DST|20260328090000||ADT^A01|CTRL|P|2.5\rPID|1",
        )
    )

    assert "MSA|AA|CTRL" in ack
    assert writer.closed is True
    assert writer.written.startswith(b"\x0b")


def test_stop_mllp_server_handles_none_and_server_instance():
    class FakeServer:
        def __init__(self):
            self.closed = False
            self.waited = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            self.waited = True

    asyncio.run(stop_mllp_server(None))
    server = FakeServer()
    asyncio.run(stop_mllp_server(server))
    assert server.closed is True
    assert server.waited is True


def test_start_mllp_server_bind_error_is_raised(monkeypatch):
    class DummyEndpoint:
        id = 1
        name = "dummy"

    async def _fake_start_server(*_args, **_kwargs):
        raise OSError("bind failed")

    monkeypatch.setattr("asyncio.start_server", _fake_start_server)

    async def _on_message(_msg, _session, _endpoint):
        return "MSH|^~\\&|ACK|ACK|SRC|SRC|20260328090000||ACK^A01|A1|P|2.5\rMSA|AA|CTRL"

    try:
        asyncio.run(start_mllp_server("127.0.0.1", 9999, _on_message, DummyEndpoint(), lambda: None))
        raised = False
    except OSError:
        raised = True

    assert raised is True


def test_validate_message_structure_detects_missing_required_fields():
    msg = "MSH|^~\\&|||DST_APP|DST_FAC|20260328090000||ADT^A01|CTRL|P|2.5\rPID|1"
    ok, err, msh = _validate_message_structure(msg)

    assert ok is False
    assert msh is None
    assert "Missing required MSH fields" in (err or "")


def test_on_message_inbound_async_rejects_non_hl7_message(session):
    ack = on_message_inbound("NOT_A_HL7_MESSAGE", session, None)

    assert isinstance(ack, dict)
    assert ack["status"] == "error"
    assert "MSA|AR" in ack["ack"]


def test_on_message_inbound_async_rejects_unsupported_type(session):
    msg = _base_msh("ORM^O01", "CTRL_ORM")
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "error"
    assert "MSA|AE|CTRL_ORM" in result["ack"]
    assert "Unsupported message type" in result["ack"]


def test_on_message_inbound_async_requires_zbe_for_movement(session):
    msg = _base_msh("ADT^A01", "CTRL_NO_ZBE") + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\rPV1|1|I"
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "error"
    assert "MSA|AE|CTRL_NO_ZBE" in result["ack"]
    assert "Segment ZBE obligatoire" in result["ack"]


def test_on_message_inbound_async_adt_handler_error_is_propagated(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return False, "mocked handler failure"

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A01", "CTRL_ADT_OK")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^UF^^^7700||H\r"
    )
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "error"
    assert "MSA|AE|CTRL_ADT_OK" in result["ack"]


def test_on_message_inbound_async_mfn_m05_success_logs_processed(session, monkeypatch):
    def _fake_process_mfn_message(_msg, _session):
        return [{"status": "success"}, {"status": "success"}]

    monkeypatch.setattr("app.services.mfn_structure.process_mfn_message", _fake_process_mfn_message)

    msg = _base_msh("MFN^M05", "CTRL_MFN") + "MFI|TEST"
    ack = on_message_inbound(msg, session, None)

    assert ack["status"] == "success"
    assert "MSA|AA|CTRL_MFN" in ack["ack"]
    assert "MFN M05 processed" in ack["ack"]

    latest = session.exec(select(MessageLog).order_by(MessageLog.id.desc())).first()
    assert latest is not None
    assert latest.correlation_id == "CTRL_MFN"
    assert latest.status == "processed"
    assert latest.kind == "MLLP"


def test_on_message_inbound_async_mfn_m05_error_logs_error(session, monkeypatch):
    def _fake_process_mfn_message(_msg, _session):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.mfn_structure.process_mfn_message", _fake_process_mfn_message)

    msg = _base_msh("MFN^M05", "CTRL_MFN_ERR") + "MFI|TEST"
    ack = on_message_inbound(msg, session, None)

    assert ack["status"] == "error"
    assert "MSA|AE|CTRL_MFN_ERR" in ack["ack"]
    assert "MFN M05 error" in ack["ack"]

    latest = session.exec(select(MessageLog).order_by(MessageLog.id.desc())).first()
    assert latest is not None
    assert latest.correlation_id == "CTRL_MFN_ERR"
    assert latest.status == "error"


def test_on_message_inbound_async_a01_nominal_returns_aa(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A01", "CTRL_A01")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^UF^^^7700||H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_A01" in result["ack"]


def test_on_message_inbound_async_a03_nominal_returns_aa(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A03", "CTRL_A03")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|2^SYS^1.2.3^ISO|20260328100000||INSERT|N||^^^^^^UF^^^7700||H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_A03" in result["ack"]


def test_on_message_inbound_async_a11_cancel_missing_target_is_rejected(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A11", "CTRL_A11")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|3^SYS^1.2.3^ISO|20260328110000||CANCEL|N||^^^^^^UF^^^7700||H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_A11" in result["ack"]
    assert "ZBE-6 trigger original requis" in result["ack"]


def test_on_message_inbound_async_a40_requires_mrg(session):
    msg = (
        _base_msh("ADT^A40", "CTRL_A40_NO_MRG")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_A40_NO_MRG" in result["ack"]
    assert "Segment MRG obligatoire" in result["ack"]


def test_on_message_inbound_async_a40_nominal_returns_aa(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A40", "CTRL_A40_OK")
        + "PID|1||SURV123^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "MRG|SRC999^^^SYS&1.2.3&ISO^PI\r"
        + "PV1|1|I|WARD\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_A40_OK" in result["ack"]


def test_on_message_inbound_async_z99_success_returns_aa(session, monkeypatch):
    monkeypatch.setattr("app.services.transport_inbound._validate_z99_original_message", lambda _msg, _session: None)
    monkeypatch.setattr("app.services.transport_inbound._handle_z99_updates", lambda _msg, _session: None)

    msg = (
        _base_msh("ADT^Z99", "CTRL_Z99_OK")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "Z99|MOUVEMENT|1|status|active\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_Z99_OK" in result["ack"]
    assert "Z99 updates applied" in result["ack"]


def test_on_message_inbound_async_z99_rejects_when_original_missing(session, monkeypatch):
    monkeypatch.setattr(
        "app.services.transport_inbound._validate_z99_original_message",
        lambda _msg, _session: "Message original introuvable",
    )

    msg = (
        _base_msh("ADT^Z99", "CTRL_Z99_BAD")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "Z99|MOUVEMENT|1|status|active\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AR|CTRL_Z99_BAD" in result["ack"]
    assert "Message original introuvable" in result["ack"]


def test_on_message_inbound_async_idempotence_returns_previous_ack(session):
    previous_ack = "MSH|^~\\&|DST|DST|SRC|SRC|20260328090000||ACK^A01|ACK1|P|2.5\rMSA|AA|CTRL_DUP\r"
    log = MessageLog(
        direction="in",
        kind="MLLP",
        correlation_id="CTRL_DUP",
        status="processed",
        payload="old",
        ack_payload=previous_ack,
        created_at=datetime.now(timezone.utc),
    )
    session.add(log)
    session.commit()

    msg = _base_msh("ADT^A01", "CTRL_DUP") + "PID|1||12345^^^SYS&1.2.3&ISO^PI\rPV1|1|I\rZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^UF^^^7700||H\r"
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "success"
    assert result["ack"] == previous_ack


def test_on_message_inbound_async_strict_ej_rejects_a08(session):
    class EJ:
        strict_pam_fr = True

    class Endpoint:
        id = 1
        entite_juridique = EJ()
        entite_juridique_id = None
        pam_validate_enabled = False
        pam_validate_mode = "warn"
        pam_profile = "IHE_PAM_FR"

    msg = _base_msh("ADT^A08", "CTRL_A08") + "PID|1||12345^^^SYS&1.2.3&ISO^PI\rPV1|1|I\rZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^UF^^^7700||H\r"
    result = on_message_inbound(msg, session, Endpoint())

    assert result["status"] == "error"
    assert "MSA|AE|CTRL_A08" in result["ack"]
    assert "A08 désactivé" in result["ack"]


def test_on_message_inbound_async_validator_reject_mode_returns_ae(session, monkeypatch):
    class Issue:
        def __init__(self, message):
            self.message = message

    class ValidationResult:
        level = "fail"
        issues = [Issue("profil non conforme")]

        def to_dict(self):
            return {"issues": [{"code": "X", "message": "profil non conforme", "severity": "error"}]}

    class Endpoint:
        id = 2
        entite_juridique = None
        entite_juridique_id = None
        pam_validate_enabled = True
        pam_validate_mode = "reject"
        pam_profile = "IHE_PAM_FR"

    monkeypatch.setattr("app.services.transport_inbound.validate_pam", lambda *_args, **_kwargs: ValidationResult())

    msg = _base_msh("ADT^A01", "CTRL_REJECT") + "PID|1||12345^^^SYS&1.2.3&ISO^PI\rPV1|1|I\rZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^UF^^^7700||H\r"
    result = on_message_inbound(msg, session, Endpoint())

    assert result["status"] == "error"
    assert "MSA|AE|CTRL_REJECT" in result["ack"]
    assert "Validation IHE PAM échouée" in result["ack"]

    latest = session.exec(select(MessageLog).order_by(MessageLog.id.desc())).first()
    assert latest is not None
    assert latest.status == "rejected"


def test_on_message_inbound_async_validator_exception_sets_warn_and_continues(session, monkeypatch):
    class Endpoint:
        id = 3
        entite_juridique = None
        entite_juridique_id = None
        pam_validate_enabled = False
        pam_validate_mode = "warn"
        pam_profile = "IHE_PAM_FR"

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.validate_pam", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("validator crash")))
    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = _base_msh("ADT^A01", "CTRL_WARN") + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\rPV1|1|I|WARD\rZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^UF^^^7700||H\r"
    result = on_message_inbound(msg, session, Endpoint())

    assert result["status"] == "success"
    assert "MSA|AA|CTRL_WARN" in result["ack"]

    latest = session.exec(select(MessageLog).order_by(MessageLog.id.desc())).first()
    assert latest is not None
    assert latest.pam_validation_status == "warn"


def test_on_message_inbound_async_update_without_existing_on_admission_falls_back_to_insert(session, monkeypatch):
    class Endpoint:
        id = 4
        entite_juridique = None
        entite_juridique_id = None
        pam_validate_enabled = False
        pam_validate_mode = "warn"
        pam_profile = "IHE_PAM_FR"

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    # UPDATE sur trigger admission A01 sans mouvement existant => fallback insert attendu
    msg = _base_msh("ADT^A01", "CTRL_UPD_FALLBACK") + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\rPV1|1|I|WARD\rZBE|999^SYS^1.2.3^ISO|20260328090000||UPDATE|N|A01|^^^^^^UF^^^7700||H\r"
    result = on_message_inbound(msg, session, Endpoint())

    assert result["status"] == "success"
    assert "MSA|AA|CTRL_UPD_FALLBACK" in result["ack"]


def test_on_message_inbound_async_z99_reject_ack_from_handler(session, monkeypatch):
    monkeypatch.setattr("app.services.transport_inbound._validate_z99_original_message", lambda _msg, _session: None)
    monkeypatch.setattr(
        "app.services.transport_inbound._handle_z99_updates",
        lambda _msg, _session: build_ack(_msg, ack_code="AE", text="Z99 rejet applicatif"),
    )

    msg = (
        _base_msh("ADT^Z99", "CTRL_Z99_REJECT")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "Z99|MOUVEMENT|1|status|cancelled\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_Z99_REJECT|Z99 rejet applicatif" in result["ack"]


def test_on_message_inbound_async_z99_handler_exception_returns_ae(session, monkeypatch):
    monkeypatch.setattr("app.services.transport_inbound._validate_z99_original_message", lambda _msg, _session: None)
    monkeypatch.setattr(
        "app.services.transport_inbound._handle_z99_updates",
        lambda _msg, _session: (_ for _ in ()).throw(RuntimeError("z99 boom")),
    )

    msg = (
        _base_msh("ADT^Z99", "CTRL_Z99_EXC")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "Z99|MOUVEMENT|1|status|active\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_Z99_EXC" in result["ack"]
    assert "Z99 processing failed" in result["ack"]


def test_on_message_inbound_async_invalid_transition_returns_ae(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (False, "Transition interdite"))

    msg = (
        _base_msh("ADT^A03", "CTRL_BAD_TRANS")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|2^SYS^1.2.3^ISO|20260328100000||INSERT|N||^^^^^^^^^7701|^^^^^^^^^7702|H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_BAD_TRANS|Transition interdite" in result["ack"]


def test_on_message_inbound_async_valueerror_path_returns_ae(session, monkeypatch):
    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr(
        "app.services.transport_inbound.validate_transition",
        lambda _prev, _trig: (_ for _ in ()).throw(ValueError("invalid transition payload")),
    )

    msg = (
        _base_msh("ADT^A01", "CTRL_VALERR")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^^^^7701|^^^^^^^^^7702|H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_VALERR" in result["ack"]
    assert "Validation error" in result["ack"]


def test_on_message_inbound_async_route_exception_returns_ar_and_error_log(session, monkeypatch):
    async def _raise_route(*_args, **_kwargs):
        raise RuntimeError("routing crashed")

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _raise_route)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A01", "CTRL_ROUTE_EXC")
        + "PID|1||12345^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|1^SYS^1.2.3^ISO|20260328090000||INSERT|N||^^^^^^^^^7701|^^^^^^^^^7702|H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AR|CTRL_ROUTE_EXC" in result["ack"]
    assert "System error" in result["ack"]

    latest = session.exec(
        select(MessageLog)
        .where(MessageLog.correlation_id == "CTRL_ROUTE_EXC")
        .order_by(MessageLog.id.desc())
    ).first()
    assert latest is not None
    assert latest.status == "error"
    assert "MSA|AR|CTRL_ROUTE_EXC" in (latest.ack_payload or "")


def test_on_message_inbound_async_cancel_existing_mouvement_marks_cancelled(session, monkeypatch):
    existing_mvt = _seed_patient_graph_with_mouvement(session, identifier="PAT_CANCEL", trigger_event="A01")

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A11", "CTRL_CANCEL_OK")
        + "PID|1||PAT_CANCEL^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + f"ZBE|{existing_mvt.mouvement_seq}^SYS^1.2.3^ISO|20260328110000||CANCEL|N|A01|^^^^^^^^^7701|^^^^^^^^^7702|H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_CANCEL_OK" in result["ack"]

    updated = session.exec(select(type(existing_mvt)).where(type(existing_mvt).id == existing_mvt.id)).first()
    assert updated is not None
    assert updated.status == "cancelled"


def test_on_message_inbound_async_update_existing_mouvement_updates_fields(session, monkeypatch):
    existing_mvt = _seed_patient_graph_with_mouvement(session, identifier="PAT_UPDATE", trigger_event="A01")

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A08", "CTRL_UPDATE_OK")
        + "PID|1||PAT_UPDATE^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + f"ZBE|{existing_mvt.mouvement_seq}^SYS^1.2.3^ISO|20260328113000||UPDATE|Y|A01|UFMED^^^^^^^^^7701|UFSOINS^^^^^^^^^7702|M\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_UPDATE_OK" in result["ack"]

    updated = session.exec(select(type(existing_mvt)).where(type(existing_mvt).id == existing_mvt.id)).first()
    assert updated is not None
    assert updated.action == "UPDATE"
    assert updated.original_trigger == "A01"
    assert updated.is_historic is True
    assert updated.uf_responsabilite == "7701"
    assert updated.uf_soins_code == "7702"
    assert updated.uf_soins_label == "UFSOINS"
    assert updated.nature == "M"


def test_on_message_inbound_async_previous_event_found_by_dossier_account_number(session, monkeypatch):
    graph = _seed_patient_graph(session, identifier="PAT_DOSSIER", trigger_event="A03")
    captured = {}

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    def _capture_transition(previous_event, trigger):
        captured["previous_event"] = previous_event
        captured["trigger"] = trigger
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", _capture_transition)
    monkeypatch.setattr(
        "app.services.transport_inbound.parse_pid",
        lambda _msg: {
            "account_number": str(graph["dossier"].dossier_seq),
            "identifiers": [["PAT_DOSSIER^^^SYS&1.2.3&ISO^PI"]],
        },
    )
    monkeypatch.setattr("app.services.transport_inbound.parse_pv1", lambda _msg: {"visit_number": None})
    monkeypatch.setattr("app.services.transport_inbound.parse_zbe", lambda _msg: {"action": None, "is_historic": False})
    monkeypatch.setattr("app.services.transport_inbound._parse_nk1_segments", lambda _msg: {})

    msg = _base_msh("ADT^A28", "CTRL_LOOKUP_DOSSIER") + "PID|1||PAT_DOSSIER^^^SYS&1.2.3&ISO^PI\r"
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "success"
    assert captured["previous_event"] == "A03"
    assert captured["trigger"] == "A28"


def test_on_message_inbound_async_previous_event_found_by_visit_number(session, monkeypatch):
    graph = _seed_patient_graph(session, identifier="PAT_VISIT", trigger_event="A01")
    captured = {}

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    def _capture_transition(previous_event, trigger):
        captured["previous_event"] = previous_event
        captured["trigger"] = trigger
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", _capture_transition)
    monkeypatch.setattr(
        "app.services.transport_inbound.parse_pid",
        lambda _msg: {
            "account_number": None,
            "identifiers": [["PAT_VISIT^^^SYS&1.2.3&ISO^PI"]],
        },
    )
    monkeypatch.setattr(
        "app.services.transport_inbound.parse_pv1",
        lambda _msg: {"visit_number": str(graph["venue"].venue_seq)},
    )
    monkeypatch.setattr("app.services.transport_inbound.parse_zbe", lambda _msg: {"action": None, "is_historic": False})
    monkeypatch.setattr("app.services.transport_inbound._parse_nk1_segments", lambda _msg: {})

    msg = _base_msh("ADT^A28", "CTRL_LOOKUP_VISIT") + "PID|1||PAT_VISIT^^^SYS&1.2.3&ISO^PI\r"
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "success"
    assert captured["previous_event"] == "A01"
    assert captured["trigger"] == "A28"


def test_on_message_inbound_async_previous_event_fallback_by_patient(session, monkeypatch):
    _seed_patient_graph(session, identifier="PAT_FALLBACK", trigger_event="A21")
    captured = {}

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    def _capture_transition(previous_event, trigger):
        captured["previous_event"] = previous_event
        captured["trigger"] = trigger
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", _capture_transition)
    monkeypatch.setattr(
        "app.services.transport_inbound.parse_pid",
        lambda _msg: {
            "account_number": None,
            "identifiers": [["PAT_FALLBACK^^^SYS&1.2.3&ISO^PI"]],
        },
    )
    monkeypatch.setattr("app.services.transport_inbound.parse_pv1", lambda _msg: {"visit_number": None})
    monkeypatch.setattr("app.services.transport_inbound.parse_zbe", lambda _msg: {"action": None, "is_historic": False})
    monkeypatch.setattr("app.services.transport_inbound._parse_nk1_segments", lambda _msg: {})

    msg = _base_msh("ADT^A28", "CTRL_LOOKUP_PATIENT") + "PID|1||PAT_FALLBACK^^^SYS&1.2.3&ISO^PI\r"
    result = on_message_inbound(msg, session, None)

    assert result["status"] == "success"
    assert captured["previous_event"] == "A21"
    assert captured["trigger"] == "A28"


def test_on_message_inbound_callable_running_loop_uses_thread_execution_path(session, monkeypatch):
    async def _fake_async(_msg, _session, _endpoint):
        return "MSH|^~\\&|ACK|ACK|SRC|SRC|20260328090000||ACK^A01|A1|P|2.5\rMSA|AA|CTRL_LOOP\r"

    monkeypatch.setattr(on_message_inbound, "_async", _fake_async)

    async def _invoke_in_running_loop():
        return on_message_inbound("MSH|^~\\&|SRC|SRC|DST|DST|20260328090000||ADT^A01|CTRL_LOOP|P|2.5\r", session, None)

    result = asyncio.run(_invoke_in_running_loop())
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_LOOP" in result["ack"]


def test_on_message_inbound_async_update_without_movement_id_and_prior_history_rejects(session, monkeypatch):
    _seed_patient_graph(session, identifier="PAT_PRIOR", trigger_event="A01")

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A01", "CTRL_PRIOR_REJECT")
        + "PID|1||PAT_PRIOR^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE||20260328090000||UPDATE|N|A01|^^^^^^^^^7701|^^^^^^^^^7702|H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "error"
    assert "MSA|AE|CTRL_PRIOR_REJECT|ZBE-1 identifiant mouvement requis" in result["ack"]


def test_on_message_inbound_async_cancel_by_type_lookup_marks_cancelled(session, monkeypatch):
    existing_mvt = _seed_patient_graph_with_mouvement(session, identifier="PAT_TYPE_LOOKUP", trigger_event="A01")
    existing_mvt.type = "LEGACY-MVT-KEY"
    session.add(existing_mvt)
    session.commit()

    async def _fake_route_message(_session, _trigger, _pid_data, _pv1_data, message=None, ej_id=None):
        return True, None

    monkeypatch.setattr("app.services.transport_inbound.IHEMessageRouter.route_message", _fake_route_message)
    monkeypatch.setattr("app.services.transport_inbound.validate_transition", lambda _prev, _trig: (True, None))

    msg = (
        _base_msh("ADT^A11", "CTRL_TYPE_LOOKUP")
        + "PID|1||PAT_TYPE_LOOKUP^^^SYS&1.2.3&ISO^PI||DOE^JOHN||19800101|M\r"
        + "PV1|1|I|WARD\r"
        + "ZBE|LEGACY-MVT-KEY|20260328110000||CANCEL|N|A01|^^^^^^^^^7701|^^^^^^^^^7702|H\r"
    )

    result = on_message_inbound(msg, session, None)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_TYPE_LOOKUP" in result["ack"]

    updated = session.exec(select(type(existing_mvt)).where(type(existing_mvt).id == existing_mvt.id)).first()
    assert updated is not None
    assert updated.status == "cancelled"


def test_on_message_inbound_callable_uses_threadsafe_submit_path(session, monkeypatch):
    class FakeFuture:
        def result(self, timeout=None):
            return "MSH|^~\\&|ACK|ACK|SRC|SRC|20260328090000||ACK^A01|A1|P|2.5\rMSA|AA|CTRL_THREADSAFE\r"

    class FakeLoop:
        def is_running(self):
            return True

    class FakePolicy:
        def __init__(self, loop):
            self._loop = loop

        def get_event_loop(self):
            return self._loop

    async def _fake_async(_msg, _session, _endpoint):
        return "unused"

    fake_running_loop = object()
    fake_loop = FakeLoop()

    def _fake_submit(coro, loop):
        coro.close()
        assert loop is fake_loop
        return FakeFuture()

    monkeypatch.setattr(on_message_inbound, "_async", _fake_async)
    monkeypatch.setattr("asyncio.get_running_loop", lambda: fake_running_loop)
    monkeypatch.setattr("asyncio.get_event_loop_policy", lambda: FakePolicy(fake_loop))
    monkeypatch.setattr("asyncio.run_coroutine_threadsafe", _fake_submit)

    result = on_message_inbound("MSH|^~\\&|SRC|SRC|DST|DST|20260328090000||ADT^A01|CTRL_THREADSAFE|P|2.5\r", session, None)
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert "MSA|AA|CTRL_THREADSAFE" in result["ack"]


def test_on_message_inbound_callable_returns_coroutine_when_thread_path_fails(session, monkeypatch):
    class FakeLoop:
        def is_running(self):
            return False

    class FakePolicy:
        def get_event_loop(self):
            return FakeLoop()

    async def _fake_async(_msg, _session, _endpoint):
        return "MSH|^~\\&|ACK|ACK|SRC|SRC|20260328090000||ACK^A01|A1|P|2.5\rMSA|AA|CTRL_CORO\r"

    monkeypatch.setattr(on_message_inbound, "_async", _fake_async)
    monkeypatch.setattr("asyncio.get_running_loop", lambda: object())
    monkeypatch.setattr("asyncio.get_event_loop_policy", lambda: FakePolicy())

    class FailingThread:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("thread start blocked")

    import threading

    monkeypatch.setattr(threading, "Thread", FailingThread)

    result = on_message_inbound("MSH|^~\\&|SRC|SRC|DST|DST|20260328090000||ADT^A01|CTRL_CORO|P|2.5\r", session, None)
    assert asyncio.iscoroutine(result)
    result.close()


def test_on_message_inbound_callable_await_dunder_raises_typeerror():
    try:
        on_message_inbound.__await__()
        raised = False
    except TypeError as exc:
        raised = True
        assert "on_message_inbound_async" in str(exc)

    assert raised is True
