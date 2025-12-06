import asyncio
import pytest
import time
from datetime import datetime
from pathlib import Path


@pytest.mark.xfail(reason="Test files in range 1117926658-1117926702 do not exist in tests/exemples/Fichier_test_pam")
@pytest.mark.usefixtures("setup_database")
def test_hospitalisation_roundtrip_files(monkeypatch):
    """Send a sequence of production HL7 messages representing a hospitalization.

    Reads files from tests/exemples/Fichier_test_pam/ in alphabetical order and selects
    files from 1117926658.hl7 to 1117926702.hl7 inclusive. Sends them through the
    inbound pipeline and asserts MessageLog rows and emitted HL7 are created.
    """
    sent_payloads = []

    async def fake_send_mllp(host, port, hl7_message):
        sent_payloads.append(hl7_message)
        await asyncio.sleep(0)
        return "MSH|^~\\&|MEDBRIDGE|POC|SRC-PAM|SRC|20251101000000||ACK|ACK1|P|2.5\rMSA|AA|MSG00001"

    monkeypatch.setattr("app.services.mllp.send_mllp", fake_send_mllp)
    try:
        monkeypatch.setattr("app.services.structure_emit.send_mllp", fake_send_mllp)
    except Exception:
        pass

    from app.db import engine
    from sqlmodel import Session as SQLSession
    from app.models_shared import SystemEndpoint, MessageLog
    from app.models_structure import EntiteJuridique
    from app.services.transport_inbound import on_message_inbound
    from app.services.pam_validation import validate_pam
    # Ensure entity event listeners are registered so emissions are scheduled
    try:
        import os
        os.environ.setdefault('TESTING', '1')
        from app.services.entity_events import register_entity_events
        register_entity_events()
    except Exception:
        pass

    base = Path(__file__).parent.parent / "exemples" / "Fichier_test_pam"
    assert base.exists(), f"Corpus folder not found: {base}"

    # Collect files in alphabetical order and filter range
    files = sorted([p for p in base.iterdir() if p.is_file() and p.suffix in ('.hl7', '.txt')])
    selected = [p for p in files if '1117926658' <= p.name <= '1117926702']
    assert selected, "No files selected in the requested range"

    with SQLSession(engine) as session:
        # create a simple sender endpoint to trigger emission
        ej = EntiteJuridique(name='EJ Hosp', finess_ej='222222222', is_active=True)
        session.add(ej)
        session.commit()

        ep = SystemEndpoint(name='EP HOSP', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2581, entite_juridique_id=ej.id)
        session.add(ep)
        session.commit()

        # also add a global endpoint (no entite_juridique_id) so emission code will
        # include a sender reachable by the emit_to_senders filtering logic
        epg = SystemEndpoint(name='EP GLOBAL HOSP', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2582)
        session.add(epg)
        session.commit()

        start = datetime.utcnow()

        for p in selected:
            text = p.read_text(encoding='utf-8')
            res = on_message_inbound(text, session, None)
            if asyncio.iscoroutine(res):
                ack = asyncio.get_event_loop().run_until_complete(res)
            else:
                ack = res.get('ack') if isinstance(res, dict) else str(res)

            # structural validation (should be a boolean is_valid)
            val = validate_pam(text, direction='inbound')
            assert isinstance(val.is_valid, bool)
            # allow warnings, fail only on errors
            if not val.is_valid and val.level == 'error':
                issues = [f"{i.code}:{i.severity}:{i.message}" for i in val.issues]
                pytest.fail(f"Message structural validation failed for {p.name}: " + ';'.join(issues))

        # wait for MessageLog entries
        end = time.time() + 10
        logs = []
        while time.time() < end:
            from sqlmodel import select
            logs = session.exec(select(MessageLog).where(MessageLog.created_at >= start)).all()
            if logs and sent_payloads:
                break
            time.sleep(0.05)

        assert logs, 'No MessageLog entries created during hospitalization scenario'
        assert sent_payloads, 'No HL7 sent captured during hospitalization scenario'

        # basic smoke-check: ensure at least one outbound HL7 contains ZBE segment
        assert any('ZBE|' in s for s in sent_payloads), 'No outbound PAM ZBE found in emitted HL7s'

    # additional content checks: at least one emitted HL7 has PV1 and PID-3 authority (CPAGE expected)
    assert any('PV1|' in s for s in sent_payloads), 'No PV1 segment found in emitted HL7s'
    # look for CPAGE authority in PID-3 (e.g., 90001...^^^CPAGE&...)
    assert any('^^^CPAGE' in s for s in sent_payloads), 'No PID-3 CPAGE authority pattern found in emitted HL7s'

    # Persist emitted HL7 payloads for manual inspection under tests/artifacts/hospitalisation
    artifacts_dir = Path(__file__).parent.parent / 'artifacts' / 'hospitalisation'
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for i, payload in enumerate(sent_payloads, start=1):
        # derive a safe filename prefix from control id if present
        control = None
        try:
            # MSH|...|...|...|...|...|2025...||ADT^A05|<control_id>|...
            first_line = payload.split('\r', 1)[0]
            parts = first_line.split('|')
            if len(parts) > 9:
                control = parts[9]
        except Exception:
            control = None
        fname = f"emitted_{i:02d}" + (f"_{control}" if control else "") + ".hl7"
        (artifacts_dir / fname).write_text(payload, encoding='utf-8')
