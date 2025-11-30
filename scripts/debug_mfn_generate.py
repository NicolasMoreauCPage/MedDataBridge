"""Debug helper: import MFN examples and generate full MFN for a selected EG.

Writes a full MFN to tmp/generated/mfn/ and prints simple diagnostics about relations.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import session_factory, engine
from sqlmodel import SQLModel, select
from app.services.mfn_structure import process_mfn_message, generate_mfn_message
from app.utils.atomic_write import write_atomic_text

MFN_DIR = ROOT / "tests" / "exemples" / "mfn"


def import_mfn_files(session):
    candidates = sorted(MFN_DIR.glob("*.hl7"))
    mfn_files = []
    for f in candidates:
        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = f.read_text(encoding="latin-1")
            except Exception:
                continue
        if "MFN^M05" in content:
            mfn_files.append((f.name, content))
    results = []
    for name, content in mfn_files:
        print(f"Importing MFN file: {name}")
        try:
            res = process_mfn_message(content, session=session, multi_pass=True)
            results.append((name, len(res)))
        except Exception as e:
            print(f"Error importing {name}: {e}")
            results.append((name, 'error'))
    return results


def main():
    if os.getenv("TESTING", "0") in ("1", "true", "True"):
        SQLModel.metadata.create_all(engine)

    with session_factory() as session:
        import_results = import_mfn_files(session)
        print("Import results:", import_results)

        # pick first EntiteGeographique
        try:
            from app.models_structure import EntiteGeographique, Pole, Service
            egs = session.exec(select(EntiteGeographique)).all()
            if not egs:
                print("No EntiteGeographique found in DB after import")
                return
            eg = egs[0]
            print(f"Selected EG: identifier={eg.identifier}, id={eg.id}, name={eg.name}")

            # print summary of related entities
            poles = session.exec(select(Pole).where(Pole.entite_geo_id == eg.id)).all()
            print(f"Poles count: {len(poles)}")
            svc_count = 0
            for p in poles:
                svcs = session.exec(select(Service).where(Service.pole_id == p.id)).all()
                svc_count += len(svcs)
            print(f"Services count (under poles): {svc_count}")

            # generate full MFN for this EG
            msg = generate_mfn_message(session, eg_identifier=getattr(eg, 'identifier', None), collapse_virtual=False)
            out_dir = ROOT / 'tmp' / 'generated' / 'mfn'
            out_dir.mkdir(parents=True, exist_ok=True)
            basename = f"mfn_full_{eg.identifier}"
            final = write_atomic_text(out_dir, basename, msg, extension='.hl7')
            print(f"Wrote MFN full to {final}")

            # also print whether LRL exists in generated message
            has_lrl = 'LRL|' in msg
            print(f"Generated MFN contains LRL segments: {has_lrl}")
            # print first 80 lines for quick inspection
            lines = msg.splitlines()
            for i, line in enumerate(lines[:80]):
                print(f"{i+1:03}: {line}")

        except Exception as e:
            print("Error during EG selection/generation:", e)


if __name__ == '__main__':
    main()
