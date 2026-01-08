#!/usr/bin/env python3
"""Extract PID-13 XTN use/equipment tokens from example HL7 files.
Writes tools/pid13_tokens.json with counts and a suggested comma-separated allow-list.
"""
import os
import json
from collections import Counter

BASE = os.path.join(os.path.dirname(__file__), '..')
EXAMPLES_DIR = os.path.join(BASE, 'tests', 'exemples', 'Fichier_test_pam')
OUT = os.path.join(os.path.dirname(__file__), 'pid13_tokens.json')

uses = Counter()
equips = Counter()
files_scanned = 0

if not os.path.isdir(EXAMPLES_DIR):
    print('Examples dir not found:', EXAMPLES_DIR)
    raise SystemExit(1)

for root, dirs, files in os.walk(EXAMPLES_DIR):
    for fn in sorted(files):
        if not fn.lower().endswith('.hl7') and not fn.lower().endswith('.txt') and not fn.lower().endswith('.msg'):
            # still try common extensions
            pass
        path = os.path.join(root, fn)
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception:
            continue
        if not text.strip():
            continue
        files_scanned += 1
        # split messages by MSH
        parts = text.replace('\r\n','\r').replace('\n','\r').split('\rMSH|')
        # if the file started with MSH| we lost the initial header, fix
        for i,p in enumerate(parts):
            if i==0 and p.startswith('MSH|'):
                msg = p
            else:
                msg = 'MSH|' + p
            lines = [l for l in msg.split('\r') if l.strip()]
            pid_lines = [l for l in lines if l.startswith('PID|')]
            if not pid_lines:
                continue
            pid = pid_lines[0]
            fields = pid.split('|')
            # PID-13 is index 13 (1-based), so fields[13]
            if len(fields) > 13:
                pid13 = fields[13]
                if not pid13:
                    continue
                reps = pid13.split('~')
                for rep in reps:
                    comps = rep.split('^')
                    use = comps[2].strip() if len(comps) > 2 and comps[2].strip() else None
                    equip = comps[3].strip() if len(comps) > 3 and comps[3].strip() else None
                    if use:
                        uses[use] += 1
                    if equip:
                        equips[equip] += 1

out = {
    'files_scanned': files_scanned,
    'uses': uses.most_common(),
    'equips': equips.most_common(),
    'suggested_allow_uses': ','.join([u for u,c in uses.most_common(100) if c>=1]),
    'suggested_allow_equips': ','.join([e for e,c in equips.most_common(100) if c>=1]),
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print('Wrote', OUT)
print('Files scanned:', files_scanned)
print('Unique uses:', len(uses))
print('Unique equips:', len(equips))
