"""Script: validate_pam_examples.py
Run stateless and stateful validators against HL7 example files in a directory.
Print a concise summary for files that produce issues.
"""
from sqlmodel import SQLModel, create_engine, Session
import os
import sys
from pathlib import Path

from app.services.pam_validation import validate_pam
from app.services.pam_sequence_validator import validate_pam_sequence

EXAMPLES_DIR = Path("tests/exemples/Fichier_test_pam")


def _create_memory_db():
    engine = create_engine("sqlite:///:memory:")
    # Ensure model classes are imported so metadata includes all tables
    import app.models  # noqa: F401
    import app.models_identifiers  # noqa: F401
    SQLModel.metadata.create_all(engine)
    return engine


def summarize_file(path: Path, session):
    text = path.read_text(errors="replace")
    stateless = validate_pam(text)
    stateful = validate_pam_sequence(text, session)
    issues = stateless.issues + stateful.issues
    if not issues:
        return None
    return {
        "file": str(path),
        "stateless": stateless.to_dict(),
        "stateful": stateful.to_dict(),
    }


def main(limit=None):
    engine = _create_memory_db()
    results = []
    files = sorted(EXAMPLES_DIR.glob("*.hl7"))
    if limit:
        files = files[:limit]
    with Session(engine) as session:
        for f in files:
            try:
                res = summarize_file(f, session)
            except Exception as e:
                print(f"Error processing {f}: {e}")
                continue
            if res:
                results.append(res)
    # Print summary: files with issues
    for r in results:
        print(f"\n=== {r['file']} ===")
        print("Stateless issues:")
        for it in r["stateless"]["issues"]:
            print(f" - {it['code']}: {it['message']} ({it['severity']})")
        print("Stateful issues:")
        for it in r["stateful"]["issues"]:
            print(f" - {it['code']}: {it['message']} ({it['severity']})")
    # Aggregate counts for issue codes
    stateless_counts = {}
    stateful_counts = {}
    for r in results:
        for it in r["stateless"]["issues"]:
            stateless_counts[it["code"]] = stateless_counts.get(it["code"], 0) + 1
        for it in r["stateful"]["issues"]:
            stateful_counts[it["code"]] = stateful_counts.get(it["code"], 0) + 1

    print(f"\nProcessed {len(files)} files, {len(results)} files with issues.")
    if stateless_counts:
        print('\nStateless issue counts:')
        for code, cnt in sorted(stateless_counts.items(), key=lambda x: -x[1]):
            print(f" - {code}: {cnt}")
    if stateful_counts:
        print('\nStateful issue counts:')
        for code, cnt in sorted(stateful_counts.items(), key=lambda x: -x[1]):
            print(f" - {code}: {cnt}")


if __name__ == '__main__':
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=lim)
