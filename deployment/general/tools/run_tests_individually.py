"""Run pytest tests one-by-one and save per-test reports.

Usage: python tools/run_tests_individually.py

The script will:
- Run `pytest --collect-only -q` to list node ids
- Execute each node id individually: `pytest <nodeid> -q --maxfail=1`
- Save stdout/stderr and exit code for each test under test_reports/<sanitized-nodeid>.json
- Produce a summary file test_reports/summary.json with aggregated results

Notes:
- This is intentionally slow but provides per-test artifacts useful for triage.
"""
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
import hashlib

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORT_DIR = os.path.join(ROOT, "test_reports")

os.makedirs(REPORT_DIR, exist_ok=True)

def run_cmd(cmd, cwd=ROOT):
    proc = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return proc.returncode, out, err


def collect_tests():
    print("Collecting tests with pytest --collect-only -q ...")
    code, out, err = run_cmd("pytest --collect-only -q")
    if code != 0:
        print("Failed to collect tests:\n", out, err)
        sys.exit(2)
    # Filter collected lines to node ids only. Pytest may interleave warnings on stdout;
    # nodeids typically contain '::' (module::class::test or file::test). Use that as a filter.
    nodeids = [ln.strip() for ln in out.splitlines() if ln.strip() and '::' in ln]
    # Keep only tests under the top-level `tests/` directory (user requested)
    nodeids = [n for n in nodeids if n.startswith('tests/')]
    print(f"Collected {len(nodeids)} tests")
    return nodeids

# Indices (1-based) of tests to skip. Add 682 per user request.
SKIP_INDICES = {682}


def sanitize(name: str) -> str:
    # Replace characters unsuitable for filenames
    s = name.replace("/", "__SLASH__").replace("::", "__DCC__").replace(" ", "_")
    # Truncate long names and append a short hash to avoid filesystem limits
    maxlen = 180
    if len(s) > maxlen:
        h = hashlib.sha1(s.encode('utf-8')).hexdigest()[:10]
        s = s[: maxlen - 11] + "__" + h
    return s


def run_tests_one_by_one(nodeids):
    # Load existing summary if present (resume support)
    summary_path = os.path.join(REPORT_DIR, "summary.json")
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except Exception:
            summary = {"total": len(nodeids), "passed": 0, "failed": 0, "skipped": 0, "failures": []}
    else:
        summary = {"total": len(nodeids), "passed": 0, "failed": 0, "skipped": 0, "failures": []}

    try:
        processed = 0
        for i, node in enumerate(nodeids, 1):
            if i in SKIP_INDICES:
                print(f"[{i}/{len(nodeids)}] Skipping (user request): {node}")
                summary.setdefault('skipped', 0)
                summary['skipped'] += 1
                # still create a tiny marker file for bookkeeping
                safe_name = sanitize(node)
                outfile = os.path.join(REPORT_DIR, f"{safe_name}.json")
                if not os.path.exists(outfile):
                    with open(outfile, 'w', encoding='utf-8') as f:
                        json.dump({"nodeid": node, "skipped": True}, f)
                continue
            safe_name = sanitize(node)
            outfile = os.path.join(REPORT_DIR, f"{safe_name}.json")
            if os.path.exists(outfile):
                # Skip already-run test
                processed += 1
                continue
            print(f"[{i}/{len(nodeids)}] Running: {node}")
            # Run single test
            cmd = f"pytest {shlex.quote(node)} -q --maxfail=1"
            code, out, err = run_cmd(cmd)
            result = {
                "nodeid": node,
                "exit_code": code,
                "stdout": out,
                "stderr": err,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            with open(outfile, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            if code == 0:
                summary["passed"] += 1
            else:
                summary["failed"] += 1
                summary["failures"].append(node)
            # flush summary incrementally
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            processed += 1
        print(f"Processed {processed}/{len(nodeids)} tests")
    except KeyboardInterrupt:
        print("Interrupted by user. Summary saved.")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def cleanup_old_reports():
    """Remove per-test JSON reports that are not from top-level `tests/` directory.

    This reads each JSON in REPORT_DIR and deletes it if the stored nodeid does not start with 'tests/'.
    """
    for fname in os.listdir(REPORT_DIR):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(REPORT_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            nodeid = data.get('nodeid')
            if not nodeid:
                # keep summary.json or unexpected files
                continue
            if not nodeid.startswith('tests/'):
                print(f"Removing old report not in tests/: {fname} (nodeid={nodeid})")
                os.remove(path)
        except Exception:
            # ignore invalid JSON or read errors (do not remove summary.json)
            continue


def main():
    # Clean old reports that are outside tests/ as requested
    cleanup_old_reports()
    nodeids = collect_tests()
    summary = run_tests_one_by_one(nodeids)
    print("Done. Summary:", summary)

if __name__ == '__main__':
    main()
