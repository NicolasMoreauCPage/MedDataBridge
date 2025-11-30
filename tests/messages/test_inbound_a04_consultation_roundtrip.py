import asyncio
import pytest
import time
from datetime import datetime
from sqlmodel import select


@pytest.mark.usefixtures("setup_database")
def test_inbound_a04_consultation_roundtrip(monkeypatch):
    """Inject ADT^A04 (consultation externe), ensure patient exists and emitted PAM is similar."""
    try:
        from app.services.entity_events import register_entity_events
        register_entity_events()
    except Exception:
        pass

    sent_payloads = []

    async def fake_send_mllp(host, port, hl7_message):
        sent_payloads.append(hl7_message)
        await asyncio.sleep(0)
        return "MSH|^~\\&|MEDBRIDGE|POC|SRC-PAM|SRC|20251101000000||ACK^A04|ACK1|P|2.5\rMSA|AA|MSG00001"

    monkeypatch.setattr("app.services.mllp.send_mllp", fake_send_mllp)
    try:
        monkeypatch.setattr("app.services.structure_emit.send_mllp", fake_send_mllp)
    except Exception:
        pass

    from app.db import engine
    from sqlmodel import Session as SQLSession
    from app.models_shared import SystemEndpoint, MessageLog
    from app.models_structure import EntiteJuridique, IdentifierNamespace

    # Use the supplied ADT^A04 (consultation externe)
    hl7_in = (
        "MSH|^~\\&|CPAGE|CPAGE|ANTARES|ANTARES|20251031142901||ADT^A04^ADT_A01|1117924606|P|2.5^FRA^2.11|||||FRA|8859/1\r"
        "EVN||20251031142901|20251001142800||phmo^INCONNU^INCONNU^^^^^^CPAGE&1.2.250.1.154&ISO|20251001142800\r"
        "PID|||000059475952^^^CPAGE&1.2.250.1.211.10.200.2&ISO^PI||RETRO^UN^UN^^M.^^L||19451010|M|||RUE DE LA RETRO^^DIJON^^21000^FRA^H|||||S||036298323^^^CPAGE&1.2.250.1.211.12.1.2&L^AN||||||N||||||N||PROV||890000038^^M\r"
        "PD1||||||||||||N\r"
        "PV1||O|7700|R|||101005344^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^RPPS|||||A||1|||||4159601^^^CPAGE&1.2.250.1.211.12.1.2&L^VN||||||||||||||||||||||N||^^^^^^^^RUE DE LA RETRO 21000 DIJON 100|20251001142800|||||||V\r"
        "PV2|||||||TO|||||||||||||||N||||||||||||||N||5\r"
        "ZBE|12565081^CPAGE^1.2.250.1.211.12.1.2^ISO|20251001142800||INSERT|N||^^^^^^UF^^^7700||MH\r"
        "ZFA|||||||||NA||NA\r"
        "ZFP|\r"
        "ZFV||||||RUE DE LA RETRO^^DIJON^^21000^100\r"
        "ZFD||||N\r"
        "ROL||UC|AT|101005344^PICQUE^JEAN BAPTISTE^^^^^^ADELI&2.16.840.1.113883.3.31.2.2&ISO^D^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^RPPS^D^^^RPPS|20251001142800|20991231235959\r"
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
        # Ensure there's an EJ/namespace different from CPAGE to force external handling
        ej = EntiteJuridique(name='EJ A04 Compare', finess_ej='888888888', is_active=True)
        session.add(ej)
        session.commit()

        ns = IdentifierNamespace(name='IPP-EJ-A04', system='urn:oid:1.2.250.999.2', oid='1.2.250.999.2', type='IPP', entite_juridique_id=ej.id, is_active=True)
        session.add(ns)
        session.commit()

        ep = SystemEndpoint(name='EP A04 COMP', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2590, entite_juridique_id=ej.id)
        session.add(ep)
        session.commit()

        ep_global = SystemEndpoint(name='EP GLOBAL A04', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2591)
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

        # Compare incoming PID and emitted PID: pick the emitted payload that contains the incoming identifier
        in_pid = extract_segment(hl7_in, 'PID')
        # identifier core from incoming PID-3
        import re
        m = re.search(r'PID\|[^\|]*\|[^\|]*\|([^\^\|~]+)', hl7_in)
        incoming_core_id = m.group(1) if m else None
        # find emitted payload that contains the same core identifier
        # Prefer the patient-level emission (ADT^A28 or ADT^A31) so we compare the PID built for patient
        matched_payload = None
        for p in reversed(sent_payloads):
            if incoming_core_id and incoming_core_id in p:
                # prefer patient-level MSH (ADT^A28 or ADT^A31)
                msh = extract_segment(p, 'MSH')
                if msh and ('ADT^A28' in msh or 'ADT^A31' in msh):
                    matched_payload = p
                    break
                if matched_payload is None:
                    matched_payload = p
        if not matched_payload:
            # fallback to last payload
            matched_payload = sent_payloads[-1]

        out_pid = extract_segment(matched_payload, 'PID')
        in_parsed = repo_parse_pid(hl7_in)
        out_parsed = repo_parse_pid(matched_payload)

        # Normalize parsed results
        def normalize_record(rec: dict) -> dict:
            nr = {}
            for k, v in rec.items():
                if isinstance(v, str):
                    nr[k] = v if v.strip() != "" else None
                elif isinstance(v, list):
                    new_list = []
                    for item in v:
                        if isinstance(item, dict):
                            new_item = {kk: (vv if (vv is not None and (not (isinstance(vv, str) and vv.strip() == ""))) else None) for kk, vv in item.items()}
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

        # Normalize birth_date formats: compare YYYYMMDD without separators
        def normalize_birth_date(s):
            if not s:
                return s
            return str(s).replace('-', '').replace('/', '')
        if in_parsed.get('birth_date'):
            in_parsed['birth_date'] = normalize_birth_date(in_parsed['birth_date'])
        if out_parsed.get('birth_date'):
            out_parsed['birth_date'] = normalize_birth_date(out_parsed['birth_date'])

        # Basic fields to compare
        fields = ['identifiers', 'external_id', 'family', 'given', 'middle', 'birth_date', 'gender', 'names', 'addresses', 'phones']
        diffs = []

        def norm_identifiers(id_list):
            if not id_list:
                return []
            return sorted([(cx.split('^')[0], t) for (cx, t) in id_list])

        in_ids = norm_identifiers(in_parsed.get('identifiers', []))
        out_ids = norm_identifiers(out_parsed.get('identifiers', []))
        if in_ids != out_ids:
            diffs.append(f"PID-3 identifiers differ:\n  in={in_ids}\n  out={out_ids}")

        for key in fields:
            if key == 'identifiers':
                continue
            iv = in_parsed.get(key)
            ov = out_parsed.get(key)
            if isinstance(iv, list) or isinstance(ov, list):
                if (iv or []) != (ov or []):
                    diffs.append(f"FIELD {key} differ: in={iv!r} out={ov!r}")
            else:
                if (iv or '') != (ov or ''):
                    diffs.append(f"FIELD {key} differ: in={iv!r} out={ov!r}")

        if diffs:
            raise AssertionError('Mismatch between incoming and emitted PID for A04:\n' + '\n'.join(diffs))
