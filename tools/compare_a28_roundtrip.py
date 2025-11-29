#!/usr/bin/env python3
"""Tool: injecte un ADT^A28, récupère MessageLog entrant/sortant et compare MSH/PID segments.
Usage: TESTING=1 .venv/bin/python3 tools/compare_a28_roundtrip.py
"""
import asyncio
from datetime import datetime
import time
from sqlmodel import select

from app.db import engine
from sqlmodel import Session as SQLSession

# Sample A28 message (same as in test)
HL7 = (
    "MSH|^~\\&|SRC-PAM|SRC|MEDBRIDGE|POC|20251101010101||ADT^A28|MSG00001|P|2.5\r"
    "PID|||SRC12345^^^SRC-PAM&1.2.250.1.211.99.1&ISO^PI||DOE^JOHN||19800101|M\r"
    "PV1||O|UNKNOWN||||||||||||||||||||||||||||||||||||\r"
)

from app.services.transport_inbound import on_message_inbound
from app.models_shared import MessageLog


def extract_segment(message: str, seg_name: str):
    for line in message.split('\r'):
        if line.startswith(seg_name + '|'):
            return line
    return None


def extract_pid3(pid_seg: str):
    # PID fields separated by '|', PID-3 is field 3 (0-based index 2)
    if not pid_seg:
        return None
    parts = pid_seg.split('|')
    if len(parts) < 4:
        return None
    return parts[3]


def run():
    with SQLSession(engine) as session:
        start = datetime.utcnow()
        res = on_message_inbound(HL7, session, None)
        if asyncio.iscoroutine(res):
            ack = asyncio.get_event_loop().run_until_complete(res)
            ack_str = ack if isinstance(ack, str) else str(ack)
        else:
            ack_str = res.get('ack') if isinstance(res, dict) else str(res)
        print('ACK:', ack_str)

        # wait for logs (short timeout)
        end = time.time() + 3
        logs = []
        while time.time() < end:
            q = select(MessageLog).where(MessageLog.created_at >= start)
            logs = session.exec(q).all()
            if logs:
                break
            time.sleep(0.05)

        if not logs:
            print('No MessageLog entries found')
            return

        print('Found MessageLog entries:')
        for i, l in enumerate(logs, 1):
            print(f"--- Log #{i} direction={l.direction} kind={l.kind} status={l.status} endpoint_id={l.endpoint_id}")
            print(l.payload)

        # Find inbound and outbound message payloads
        inbound = None
        outbound = None
        for l in logs:
            if l.direction == 'in':
                inbound = l.payload
            else:
                outbound = l.payload

        print('\nComparison:')
        in_msh = extract_segment(HL7, 'MSH')
        in_pid = extract_segment(HL7, 'PID')
        out_msh = extract_segment(outbound or '', 'MSH')
        out_pid = extract_segment(outbound or '', 'PID')

        print('Incoming MSH :', in_msh)
        print('Outgoing MSH :', out_msh)
        print('Incoming PID-3:', extract_pid3(in_pid))
        print('Outgoing PID-3:', extract_pid3(out_pid))

        if extract_pid3(in_pid) == extract_pid3(out_pid):
            print('\nPID-3 identical -> conforme')
        else:
            print('\nPID-3 differs -> NON conforme')


if __name__ == '__main__':
    run()
