"""Check IHE PAM examples: import each HL7 file with on_message_inbound_async and validate emitted PAM messages.

Usage: run from repo root: python3 scripts/check_pam_examples.py

This script is non-destructive: it uses the project's session factory and writes MessageLog entries as the normal pipeline does.
"""
import asyncio
from pathlib import Path
import json
import sys
import os

# Ensure project root is importable when running as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import session_factory
from sqlmodel import SQLModel
from app.db import engine
from app.services.transport_inbound import on_message_inbound_async
from app.services.pam_validation import validate_pam
from app.models_shared import MessageLog
from sqlmodel import select

EXAMPLES_DIR = ROOT / "tests" / "exemples" / "Fichier_test_pam"


def process_file(session, filepath):
    content = filepath.read_text(encoding="utf-8")
    # Call the async inbound handler
    ack = asyncio.run(on_message_inbound_async(content, session, None))
    # Find the most recent MessageLog for this control id (MSH-10) if present
    # Fallback: get latest logs
    logs = session.exec(select(MessageLog).order_by(MessageLog.id.desc()).limit(10)).all()
    return ack, logs


def main(limit=10):
    # If running in TESTING mode, ensure the in-memory tables are created.
    if os.getenv("TESTING", "0") in ("1", "true", "True"):
        SQLModel.metadata.create_all(engine)

    all_files = sorted(EXAMPLES_DIR.glob("*.hl7"))
    files = all_files if limit is None else all_files[:limit]
    if not files:
        print("Aucun fichier exemple trouvé dans", EXAMPLES_DIR)
        return 1

    results = []
    # Use explicit session factory for scripts
    with session_factory() as session:
        for f in files:
            print(f"Processing {f.name}")
            # Read file with fallback encodings to handle examples with legacy encodings
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = f.read_text(encoding="latin-1")
                except Exception as e:
                    print(f"Failed to read {f.name}: {e}")
                    results.append({
                        "file": f.name,
                        "error": f"read_error: {e}",
                        "ack": None,
                        "inbound_validation": {"ok": False, "level": "error", "issues": [{"error": str(e)}]},
                        "outbound_count": 0,
                        "outbound_logs": [],
                        "validations": [],
                    })
                    continue
            # Record last message id before processing so we can fetch new logs
            last_id_row = session.exec(select(MessageLog.id).order_by(MessageLog.id.desc()).limit(1)).first()
            last_id = int(last_id_row) if last_id_row is not None else 0

            # Validate incoming message syntax/semantics first
            try:
                inbound_val = validate_pam(content, direction="in")
                inbound_ok = inbound_val.level != "fail"
                inbound_issues = [i.__dict__ for i in inbound_val.issues]
            except Exception as e:
                inbound_ok = False
                inbound_issues = [{"error": str(e)}]

            try:
                ack, _ = process_file(session, f)
            except Exception as e:
                # Record processing error and continue
                print(f"Error processing {f.name}: {e}")
                results.append({
                    "file": f.name,
                    "error": str(e),
                    "ack": None,
                    "inbound_validation": {"ok": False, "level": "error", "issues": [{"error": str(e)}]},
                    "outbound_count": 0,
                    "outbound_logs": [],
                    "validations": [],
                })
                continue
            # Collect logs created during this processing run
            created_logs = session.exec(select(MessageLog).where(MessageLog.id > last_id).order_by(MessageLog.id.asc())).all()
            outbound = [l for l in created_logs if (l.direction == "out") or (l.kind == "MLLP" and l.status in ("sent", "ack_ok", "pending"))]
            val_results = []
            for ob in outbound:
                try:
                    v = validate_pam(ob.payload, direction="out")
                    val_results.append({"id": ob.id, "ok": v.level != "fail", "level": v.level, "issues": [i.__dict__ for i in v.issues]})
                except Exception as e:
                    val_results.append({"id": ob.id, "ok": False, "error": str(e)})
            results.append({
                "file": f.name,
                "ack": ack,
                "inbound_validation": {"ok": inbound_ok, "level": getattr(inbound_val, 'level', None), "issues": inbound_issues},
                "outbound_count": len(outbound),
                "outbound_logs": [{"id": l.id, "kind": l.kind, "status": l.status, "payload_preview": (l.payload[:200] + '...') if l.payload else ""} for l in outbound],
                "validations": val_results,
            })

    # Persist JSON results to a workspace tmp file to avoid mixing logs/JSON in stdout
    out_dir = ROOT / 'tmp'
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / 'pam_results.json'
    with out_file.open('w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"Wrote results JSON to {out_file}")
    # Simple summary
    total = len(results)
    with_out = sum(1 for r in results if r["outbound_count"] > 0)
    failed = sum(1 for r in results if any(not v.get("ok", False) for v in r["validations"]))
    print(f"Processed {total} files, {with_out} emitted outbound messages, {failed} had failing validations")
    return 0

if __name__ == "__main__":
    # Accept either an integer limit or the string 'all'
    lim = 10
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "all":
            lim = None
        else:
            try:
                lim = int(arg)
            except Exception:
                print("Argument invalide. Utilisation: scripts/check_pam_examples.py [N|all]")
                sys.exit(2)
    sys.exit(main(limit=lim))
