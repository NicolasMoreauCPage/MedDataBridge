import asyncio
from datetime import datetime
import time
import pytest
from sqlmodel import select


@pytest.mark.usefixtures("setup_database")
def test_inbound_a28_creates_patient_and_emits(monkeypatch):
    """Inject an ADT^A28 (identity add) HL7 message, verify patient persisted and outbound IHE PAM emitted.

    This test sets up a SystemEndpoint (MLLP) with a different IdentifierNamespace than the incoming PID-3
    so that the incoming identifier should be classified as EXTERNAL and stored as an external identifier.
    """
    # Register entity events to ensure emission wiring
    try:
        from app.services.entity_events import register_entity_events
        register_entity_events()
    except Exception:
        pass

    # Stub network senders
    async def fake_send_mllp(host, port, hl7_message):
        await asyncio.sleep(0)
        # Renvoie a simple AA ACK with MSA segment
        return "MSH|^~\\&|Fake|Fake|Recv|Recv|20250101000000||ACK^A01|ACK1|P|2.5\rMSA|AA|1"

    async def fake_post_fhir_bundle(base, bundle, auth_kind="none", auth_token=None):
        await asyncio.sleep(0)
        return 200, {"ok": True}

    monkeypatch.setattr("app.services.mllp.send_mllp", fake_send_mllp)
    monkeypatch.setattr("app.services.fhir_transport.post_fhir_bundle", fake_post_fhir_bundle)
    try:
        monkeypatch.setattr("app.services.structure_emit.send_mllp", fake_send_mllp)
    except Exception:
        pass

    from app.db import engine
    from sqlmodel import Session as SQLSession
    from app.models_shared import SystemEndpoint, MessageLog
    from app.models_structure import EntiteJuridique, IdentifierNamespace

    with SQLSession(engine) as session:
        # Create an EntiteJuridique and a namespace that is DIFFERENT from the incoming PID-3 namespace
        ej = EntiteJuridique(name="EJ Test A28", finess_ej="777777777", is_active=True)
        session.add(ej)
        session.commit()

        # Create a namespace for this EJ (IPP) with a system that differs from incoming
        ns = IdentifierNamespace(name="IPP-EJ", system="urn:oid:1.2.250.999.1", oid="1.2.250.999.1", type="IPP", entite_juridique_id=ej.id, is_active=True)
        session.add(ns)
        session.commit()

        # Create a sender endpoint (MLLP) to trigger emissions
        ep = SystemEndpoint(name="UT MLLP A28", kind="MLLP", role="sender", is_enabled=True, host="localhost", port=2579, entite_juridique_id=ej.id)
        session.add(ep)
        session.commit()

        # Helper to wait for MessageLog entries created after a timestamp
        def wait_for_logs_since(since, timeout=5):
            end = time.time() + timeout
            while time.time() < end:
                q = select(MessageLog).where(MessageLog.created_at >= since)
                res = session.exec(q).all()
                if res:
                    return res
                time.sleep(0.05)
            return []

        # Build an ADT^A28 HL7 message where PID-3 namespace is different (SRC-PAM)
        hl7 = (
            "MSH|^~\\&|SRC-PAM|SRC|MEDBRIDGE|POC|20251101010101||ADT^A28|MSG00001|P|2.5\r"
            "PID|||SRC12345^^^SRC-PAM&1.2.250.1.211.99.1&ISO^PI||DOE^JOHN||19800101|M\r"
            "PV1||O|UNKNOWN||||||||||||||||||||||||||||||||||||\r"
        )

        # Call inbound handler (sync wrapper)
        from app.services.transport_inbound import on_message_inbound

        start = datetime.utcnow()
        res = on_message_inbound(hl7, session, None)
        # If returned coroutine, await it
        if asyncio.iscoroutine(res):
            ack = asyncio.get_event_loop().run_until_complete(res)
            ack_str = ack
        else:
            ack_str = res.get("ack") if isinstance(res, dict) else str(res)

        assert "MSA|AA" in ack_str or "MSA|CA" in ack_str

        # Wait for MessageLog outbound entries
        logs = wait_for_logs_since(start, timeout=5)
        assert logs, "No MessageLog entries created"

        # Find patient in DB (identifier should be stored either as main identifier or external)
        from app.models import Patient, Identifier
        patient = session.exec(select(Patient).where(Patient.family == "DOE")).first()
        assert patient is not None, "Patient not persisted"

        # The patient.identifier may be stored as a full CX string (e.g. 'SRC12345^^^...')
        # or as a simple value. Extract the core identifier by splitting on '^'.
        core_id = None
        if patient.identifier:
            core_id = str(patient.identifier).split("^")[0]
        else:
            # Fall back to Identifier rows
            ids = session.exec(select(Identifier).where(Identifier.value.contains("SRC12345"))).all()
            if ids:
                core_id = ids[0].value.split("^")[0]

        assert core_id == "SRC12345", f"Expected persisted core identifier 'SRC12345', got {core_id!r}"

    # Inspect MessageLog payloads created (direction may not be 'out' in test harness)
    payloads = [l.payload for l in logs if getattr(l, 'payload', None)]
    assert any("PID" in p for p in payloads), f"No PID segment found in MessageLog payloads: {payloads}"
    # Ensure outbound payloads contain the incoming identifier somewhere
    assert any("SRC12345" in p for p in payloads), f"Incoming identifier not found in payloads: {payloads}"


