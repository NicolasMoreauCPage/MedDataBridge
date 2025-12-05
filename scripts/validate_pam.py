#!/usr/bin/env python3
"""
IHE PAM validator: checks HL7 message structure and workflow event order.
Usage:
  python3 scripts/validate_pam.py message <file.hl7>
  python3 scripts/validate_pam.py workflow <dir_with_hl7_files>
"""
import sys
import os
import re
from pathlib import Path
from collections import defaultdict

def parse_hl7_message(path):
    with open(path, encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    segments = [line.split('|') for line in lines]
    return segments

def validate_message(path):
    segments = parse_hl7_message(path)
    errors = []
    # Check required segments
    required = ['MSH', 'PID', 'PV1']
    found = {seg[0] for seg in segments}
    for req in required:
        if req not in found:
            errors.append(f"Missing required segment: {req}")
    # Check MSH-9 (message type)
    msh = next((seg for seg in segments if seg[0] == 'MSH'), None)
    if msh and (len(msh) < 9 or not msh[8]):
        errors.append("MSH-9 (message type) is missing or empty")
    # Check PID-3 (patient identifier)
    pid = next((seg for seg in segments if seg[0] == 'PID'), None)
    if pid and (len(pid) < 4 or not pid[3]):
        errors.append("PID-3 (patient identifier) is missing or empty")
    # Check PV1-2/3 (location codes)
    pv1 = next((seg for seg in segments if seg[0] == 'PV1'), None)
    if pv1:
        if len(pv1) < 3 or not pv1[2]:
            errors.append("PV1-2 (patient class) is missing or empty")
        if len(pv1) < 4 or not pv1[3]:
            errors.append("PV1-3 (assigned location) is missing or empty")
    # Optionally check ZBE presence
    if not any(seg[0].startswith('ZBE') for seg in segments):
        errors.append("No ZBE segment found (optional, but expected in PAM)")
    # Print results
    print(f"Validation results for {path}:")
    if errors:
        for err in errors:
            print(f"  ERROR: {err}")
    else:
        print("  OK: All required segments and fields present.")


def validate_workflow(directory):
    # Collect all messages, group by patient (PID-3), sort by MSH-7 (datetime)
    events = defaultdict(list)
    for file in Path(directory).glob('*.hl7'):
        segments = parse_hl7_message(file)
        pid = next((seg[3] for seg in segments if seg[0] == 'PID' and len(seg) > 3), None)
        msh = next((seg for seg in segments if seg[0] == 'MSH'), None)
        dt = msh[6] if msh and len(msh) > 6 else ''
        msg_type = msh[8] if msh and len(msh) > 8 else ''
        events[pid].append((dt, msg_type, file.name))
    # For each patient, check event order
    for pid, evs in events.items():
        evs_sorted = sorted(evs, key=lambda x: x[0])
        types = [e[1] for e in evs_sorted]
        print(f"Workflow for patient {pid}:")
        print("  Events:", types)
        # Simple rule: A01 must precede A03, no A03 before A01
        if 'A03' in ''.join(types) and 'A01' not in ''.join(types):
            print("  ERROR: Discharge (A03) before admission (A01)")
        if types and types.index('A03') < types.index('A01'):
            print("  ERROR: A03 occurs before A01")
        else:
            print("  OK: Event order plausible.")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1]
    target = sys.argv[2]
    if mode == 'message':
        validate_message(target)
    elif mode == 'workflow':
        validate_workflow(target)
    else:
        print("Unknown mode. Use 'message' or 'workflow'.")
        sys.exit(1)
