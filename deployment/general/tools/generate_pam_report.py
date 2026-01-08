#!/usr/bin/env python3
"""Generate a full PAM import report without modifying the database.

For each HL7 file in tests/exemples/Fichier_test_pam:
 - validate with PAMValidator
 - extract PV1 and ZBE raw segment lines (if present)
 - record validation errors/warnings
 - emit a summary JSON in reports/pam_import_report.json

Usage: python3 tools/generate_pam_report.py
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validators.hl7_validators import PAMValidator

BASE = Path(__file__).parent.parent
PAM_DIR = BASE / 'tests' / 'exemples' / 'Fichier_test_pam'
OUT = BASE / 'reports' / 'pam_import_report.json'

def extract_segments(text):
    txt = text.replace('\r\n','\r').replace('\n','\r')
    segs = txt.split('\r')
    pv1 = None
    zbe = None
    for s in segs:
        if s.startswith('PV1|'):
            pv1 = s
        if s.startswith('ZBE|'):
            zbe = s
    return pv1, zbe

def main():
    if not PAM_DIR.exists():
        print('PAM directory not found:', PAM_DIR)
        return 1

    files = sorted(PAM_DIR.glob('*.hl7'))
    report = {
        'checked': len(files),
        'imported_estimate': 0, # best-effort: files passing validation
        'validation_failed': 0,
        'errors': 0,
        'files': []
    }

    validator = PAMValidator()

    for p in files:
        item = {'file': p.name}
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
            result = validator.validate_message(text)
            pv1, zbe = extract_segments(text)
            item['pv1'] = pv1
            item['zbe'] = zbe
            item['is_valid'] = result.is_valid
            item['errors'] = [{'segment': e.segment, 'field': e.field, 'message': e.message, 'line': e.line_number} for e in (result.errors or [])]
            item['warnings'] = [{'segment': w.segment, 'field': w.field, 'message': w.message, 'line': w.line_number} for w in (result.warnings or [])]
            if result.is_valid:
                report['imported_estimate'] += 1
            else:
                report['validation_failed'] += 1
        except Exception as e:
            item['error'] = str(e)
            report['errors'] += 1

        report['files'].append(item)

    # write report
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Report written to', OUT)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
