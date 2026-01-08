"""Parcourt les fichiers HL7 dans tests/exemples/Fichier_test_pam/ (ordre alphabétique),
exécute validate_pam pour chaque message et validate_scenario pour les fichiers multi-message.
Ignore les fichiers sans PID (considérés outputs-only). Produit un rapport succinct sur stdout
et écrit un fichier JSON de sortie tools/validate_pam_examples_report.json.

Usage:
  .venv/bin/python tools/validate_pam_examples.py
"""

import os
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / 'tests' / 'exemples' / 'Fichier_test_pam'
REPORT_PATH = ROOT / 'tools' / 'validate_pam_examples_report.json'

# Import validators from the app
from app.services.pam_validation import validate_pam
from app.services.scenario_validation import validate_scenario


def split_messages(raw: str):
    # Split on lines that start with MSH| (keep the MSH)
    parts = re.split(r'(?=^MSH\|)', raw, flags=re.M)
    # filter empty
    msgs = [p.strip('\n\r') for p in parts if p.strip()]
    return msgs


def extract_pid3(msg: str):
    m = re.search(r'^PID\|([^\r\n]*)', msg, flags=re.M)
    if not m:
        return None
    pid_line = m.group(0)
    # get the fields
    fields = pid_line.split('|')
    if len(fields) > 3:
        return fields[3].strip()
    return None


def has_pid(msg: str):
    return bool(re.search(r'^PID\|', msg, flags=re.M))


def analyze_file(path: Path):
    raw = path.read_text(errors='ignore')
    msgs = split_messages(raw)
    if not msgs:
        return {'file': str(path), 'status': 'empty', 'messages': 0}

    # consider file "output-only" if no message contains PID
    if not any(has_pid(m) for m in msgs):
        return {'file': str(path), 'status': 'no_pid_ignored', 'messages': len(msgs)}

    per_message = []
    pid3_list = []
    creation_triggers = {'A01', 'A04', 'A28', 'A05', 'A31', 'A40'}
    first_creation_pid3 = None
    first_creation_trigger = None

    for i, m in enumerate(msgs, start=1):
        try:
            val = validate_pam(m, direction='inbound')
        except Exception as e:
            per_message.append({'message_number': i, 'status': 'validate_exception', 'error': repr(e)})
            continue
        issues = [{'code': it.code, 'severity': it.severity, 'message': it.message} for it in val.issues]
        pid3 = extract_pid3(m)
        pid3_list.append(pid3)
        per_message.append({'message_number': i, 'event': val.event, 'is_valid': val.is_valid, 'level': val.level, 'pid3': pid3, 'issues': issues})
        # detect first creation
        if not first_creation_pid3 and val.event in creation_triggers:
            first_creation_pid3 = pid3
            first_creation_trigger = val.event

    # scenario validation for multi-message files
    scen = None
    scen_summary = None
    if len(msgs) > 1:
        try:
            scen = validate_scenario('\n\n'.join(msgs), direction='inbound', profile='IHE_PAM_FR')
            scen_summary = {
                'is_valid': scen.is_valid,
                'level': scen.level,
                'n_messages': len(scen.messages),
                'workflow_issues': [{'code': it.code, 'severity': it.severity, 'message': it.message} for it in scen.workflow_issues],
                'coherence_issues': [{'code': it.code, 'severity': it.severity, 'message': it.message} for it in scen.coherence_issues]
            }
        except Exception as e:
            scen_summary = {'validate_exception': repr(e)}

    # Check that subsequent messages reuse the PID of creation when present
    pid_follow_ok = None
    if first_creation_pid3:
        # For messages after the creation, ensure their pid3 equals first_creation_pid3 when pid exists
        pid_follow_ok = True
        problems = []
        for idx, p in enumerate(pid3_list, start=1):
            if idx == 1:
                continue
            if p and p != first_creation_pid3:
                pid_follow_ok = False
                problems.append({'message_number': idx, 'pid3': p})
        pid_follow_problems = problems
    else:
        pid_follow_ok = None
        pid_follow_problems = None

    return {
        'file': str(path),
        'status': 'analyzed',
        'messages': len(msgs),
        'per_message': per_message,
        'scenario': scen_summary,
        'first_creation_pid3': first_creation_pid3,
        'first_creation_trigger': first_creation_trigger,
        'pid_follow_ok': pid_follow_ok,
        'pid_follow_problems': pid_follow_problems,
    }


def main():
    if not EXAMPLES_DIR.exists():
        print(f"Examples dir not found: {EXAMPLES_DIR}")
        return

    files = sorted([p for p in EXAMPLES_DIR.iterdir() if p.is_file()])
    report = []
    skipped = 0
    for f in files:
        res = analyze_file(f)
        report.append(res)
        # print a one-line summary
        if res.get('status') == 'no_pid_ignored':
            print(f"SKIP {f.name}: no PID (output-only) - messages={res['messages']}")
            skipped += 1
        elif res.get('status') == 'empty':
            print(f"SKIP {f.name}: empty file")
            skipped += 1
        else:
            nmsg = res['messages']
            ok_msgs = sum(1 for m in res['per_message'] if m.get('is_valid'))
            print(f"OK   {f.name}: messages={nmsg}, valid_messages={ok_msgs}/{nmsg}, scen_valid={res['scenario']['is_valid'] if res['scenario'] else 'N/A'}")
            if res['first_creation_pid3'] and res['pid_follow_ok'] is False:
                print(f"     PID follow mismatch: first_creation_pid3={res['first_creation_pid3']}, problems={res['pid_follow_problems']}")

    # write full report
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport written to {REPORT_PATH} (skipped {skipped} files)")


if __name__ == '__main__':
    main()
