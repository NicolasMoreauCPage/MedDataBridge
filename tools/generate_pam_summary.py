#!/usr/bin/env python3
"""Generate a compact summary from reports/pam_import_report.json.

Produces reports/pam_import_summary.json with counts and a small sample of
validation failures and warnings to make reviews lighter and suitable for
committing to the repo.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports' / 'pam_import_report.json'
SUMMARY = ROOT / 'reports' / 'pam_import_summary.json'


def load_report(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def make_summary(report: dict, max_samples: int = 30) -> dict:
    files = report.get('files', [])
    total = report.get('checked', len(files))
    imported = report.get('imported_estimate', None)
    validation_failed = report.get('validation_failed', None)
    errors = report.get('errors', None)

    # collect failures where is_valid is false or warnings/errors present
    failures = []
    for entry in files:
        if not entry.get('is_valid', True) or entry.get('errors') or entry.get('warnings'):
            failures.append(entry)

    # build a compact sample
    sample = []
    for e in failures[:max_samples]:
        sample.append({
            'file': e.get('file'),
            'is_valid': e.get('is_valid', True),
            'errors_count': len(e.get('errors', [])) if e.get('errors') else 0,
            'warnings_count': len(e.get('warnings', [])) if e.get('warnings') else 0,
            'pv1': bool(e.get('pv1')),
            'zbe': bool(e.get('zbe')),
            'first_warning': e.get('warnings', [None])[0],
        })

    summary = {
        'total_files_checked': total,
        'imported_estimate': imported,
        'validation_failed': validation_failed,
        'errors': errors,
        'failures_sample_count': len(failures),
        'failures_sample': sample,
    }
    return summary


def write_summary(summary: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def main():
    if not REPORT.exists():
        print(f"Report not found: {REPORT}")
        return 2
    report = load_report(REPORT)
    summary = make_summary(report)
    write_summary(summary, SUMMARY)
    print(f"Wrote summary to {SUMMARY}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
