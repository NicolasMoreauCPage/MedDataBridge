import asyncio
import pytest
import time
from datetime import datetime
from sqlmodel import select


@pytest.mark.xfail(reason="A28 triggers early return without emission (identity-only message)")
@pytest.mark.usefixtures("setup_database")
def test_inbound_a28_identity_roundtrip_compare(monkeypatch):
    """Inject ADT^A28, capture emitted HL7 and compare PID identity fields end-to-end."""
    try:
        from app.services.entity_events import register_entity_events
        register_entity_events()
    except Exception:
        pass

    sent_payloads = []

    async def fake_send_mllp(host, port, hl7_message):
        # capture payload and Renvoie AA
        sent_payloads.append(hl7_message)
        await asyncio.sleep(0)
        return "MSH|^~\\&|MEDBRIDGE|POC|SRC-PAM|SRC|20251101000000||ACK^A28|ACK1|P|2.5\rMSA|AA|MSG00001"

    monkeypatch.setattr("app.services.mllp.send_mllp", fake_send_mllp)
    # some codepaths use structure_emit.send_mllp
    try:
        monkeypatch.setattr("app.services.structure_emit.send_mllp", fake_send_mllp)
    except Exception:
        pass

    from app.db import engine
    from sqlmodel import Session as SQLSession
    from app.models_shared import SystemEndpoint, MessageLog
    from app.models_structure import EntiteJuridique, IdentifierNamespace

    # Build ADT^A28 including EVN to satisfy validators
    hl7_in = (
        "MSH|^~\\&|SRC-PAM|SRC|MEDBRIDGE|POC|20251101010101||ADT^A28|MSG00001|P|2.5\r"
        "EVN|A28|20251101010101\r"
        "PID|||SRC12345^^^SRC-PAM&1.2.250.1.211.99.1&ISO^PI||DOE^JOHN||19800101|M\r"
        "PV1||O|UNKNOWN\r"
    )

    from app.infrastructure.hl7.parsing.pid_parser import parse_pid as repo_parse_pid

    def extract_segment(message: str, seg_name: str):
        if not message:
            return None
        for line in message.split('\r'):
            if line.startswith(seg_name + '|'):
                return line
        return None

    with SQLSession(engine) as session:
        # create EJ and endpoint with different namespace to force external handling
        ej = EntiteJuridique(name='EJ Compare', finess_ej='999999999', is_active=True)
        session.add(ej)
        session.commit()

        ns = IdentifierNamespace(name='IPP-EJ', system='urn:oid:1.2.250.999.1', oid='1.2.250.999.1', type='IPP', entite_juridique_id=ej.id, is_active=True)
        session.add(ns)
        session.commit()

        ep = SystemEndpoint(name='EP COMP', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2579, entite_juridique_id=ej.id)
        session.add(ep)
        session.commit()

        # Also create a global endpoint (no entite_juridique_id) to ensure emission is triggered
        ep_global = SystemEndpoint(name='EP GLOBAL', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2580)
        session.add(ep_global)
        session.commit()

        # Call inbound
        from app.services.transport_inbound import on_message_inbound
        start = datetime.utcnow()
        res = on_message_inbound(hl7_in, session, None)
        if asyncio.iscoroutine(res):
            ack = asyncio.get_event_loop().run_until_complete(res)
            ack_str = ack if isinstance(ack, str) else str(ack)
        else:
            ack_str = res.get('ack') if isinstance(res, dict) else str(res)

        assert 'MSA|AA' in ack_str or 'MSA|CA' in ack_str

        # wait for MessageLog entries and for captured sent payload
        end = time.time() + 5
        logs = []
        while time.time() < end:
            q = select(MessageLog).where(MessageLog.created_at >= start)
            logs = session.exec(q).all()
            if logs and sent_payloads:
                break
            time.sleep(0.05)

        assert logs, 'No MessageLog entries created'
        assert sent_payloads, 'No HL7 sent captured'

        # Compare incoming PID and emitted PID
        in_pid = extract_segment(hl7_in, 'PID')
        out_pid = extract_segment(sent_payloads[-1], 'PID')
        in_parsed = repo_parse_pid(hl7_in)
        out_parsed = repo_parse_pid(sent_payloads[-1])

        # Normalize parsed results: convert empty strings to None, filter empty addresses/names/phones
        def normalize_value(v):
            if v == "" or v == []:
                return None
            return v

        def normalize_record(rec: dict) -> dict:
            nr = {}
            for k, v in rec.items():
                if isinstance(v, str):
                    nr[k] = v if v.strip() != "" else None
                elif isinstance(v, list):
                    # normalize list of dicts
                    new_list = []
                    for item in v:
                        if isinstance(item, dict):
                            new_item = {kk: (vv if (vv is not None and (not (isinstance(vv, str) and vv.strip() == ""))) else None) for kk, vv in item.items()}
                            # consider item empty if all values are None or empty
                            if any(val not in (None, "") for val in new_item.values()):
                                new_list.append(new_item)
                        else:
                            if item not in (None, ""):
                                new_list.append(item)
                    nr[k] = new_list
                else:
                    nr[k] = v
            return nr

        in_parsed = normalize_record(in_parsed)
        out_parsed = normalize_record(out_parsed)

        # Fields to compare (as supported by repository parser)
        fields = [
            'identifiers', 'external_id', 'family', 'given', 'middle', 'prefix', 'suffix',
            'birth_date', 'gender', 'address', 'city', 'state', 'postal_code', 'country',
            'phone', 'email', 'ssn', 'marital_status', 'names', 'addresses', 'phones',
            'birth_family', 'birth_address', 'birth_city', 'birth_state', 'birth_postal_code', 'birth_country', 'birth_place',
            'mobile', 'work_phone', 'identity_reliability_code', 'account_number'
        ]

        diffs = []

        # Compare identifiers specially (order-insensitive comparison on CX value and id type)
        def norm_identifiers(id_list):
            # id_list is list of tuples (cx_value, id_type) per parse_patient_identifiers
            if not id_list:
                return []
            return sorted([(cx.split('^')[0], t) for (cx, t) in id_list])

        in_ids = norm_identifiers(in_parsed.get('identifiers', []))
        out_ids = norm_identifiers(out_parsed.get('identifiers', []))
        if in_ids != out_ids:
            diffs.append(f"PID-3 identifiers differ:\n  in={in_ids}\n  out={out_ids}")

        # Compare other fields
        for key in fields:
            if key == 'identifiers':
                continue
            iv = in_parsed.get(key)
            ov = out_parsed.get(key)
            # normalize lists/dicts to comparable forms
            if isinstance(iv, list) or isinstance(ov, list):
                if (iv or []) != (ov or []):
                    diffs.append(f"FIELD {key} differ: in={iv!r} out={ov!r}")
            else:
                if (iv or '') != (ov or ''):
                    diffs.append(f"FIELD {key} differ: in={iv!r} out={ov!r}")

        if diffs:
            raise AssertionError('Identity mismatch between incoming and emitted PID:\n' + '\n'.join(diffs))
