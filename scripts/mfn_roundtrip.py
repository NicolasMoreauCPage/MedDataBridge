"""Import MFN structure examples, then run PAM examples processing in the same TESTING session.

This script is designed to be run from the repository root with TESTING=1 to use the
in-memory database. It will:
 - create DB schema if TESTING is enabled
 - import the MFN structure example files (three files in tests/exemples)
 - run the existing PAM examples processor logic (similar to scripts/check_pam_examples.py)

Usage: TESTING=1 python3 scripts/mfn_roundtrip.py
"""
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import session_factory, engine
from sqlmodel import SQLModel, select
from app.services.mfn_structure import process_mfn_message, generate_mfn_message
from app.services.transport_inbound import on_message_inbound_async
from app.services.pam_validation import validate_pam
from app.models_shared import MessageLog
from sqlmodel import select
from app.services.emit_on_create import generate_pam_hl7
from app.models import Patient, Dossier, Venue, Mouvement

MFN_DIR = ROOT / "tests" / "exemples" / "mfn"
PAM_DIR = ROOT / "tests" / "exemples" / "Fichier_test_pam"


def import_mfn_files(session):
    # Find MFN examples in tests/exemples (heuristic: files ending with .hl7 and containing 'MFN' in first line)
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
        if "MFN^M05" in content.splitlines()[0] or "MFN^M05" in content:
            mfn_files.append(f)

    # If explicit known filenames exist, prefer them
    known = [MFN_DIR / "ExempleExtractionStructure.hl7", MFN_DIR / "StructureSimple.hl7", MFN_DIR / "Structure_PR205VA1.hl7"]
    mfn_files = [f for f in known if f.exists()] or mfn_files

    results = []
    for f in mfn_files:
        print(f"Importing MFN structure file: {f.name}")
        try:
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = f.read_text(encoding="latin-1")
            res = process_mfn_message(content, session=session, multi_pass=True)
            results.append({"file": f.name, "result_count": len(res), "details": res})
        except Exception as e:
            print(f"Error importing {f.name}: {e}")
            results.append({"file": f.name, "error": str(e)})
    return results


def run_pam_checks(session, limit=None):
    # Re-implement a lightweight version of the check that runs in the same session
    files = sorted(PAM_DIR.glob("*.hl7"))
    # Allow overriding limit via env var PAM_LIMIT
    try:
        env_limit = os.getenv('PAM_LIMIT')
        if env_limit:
            limit = int(env_limit)
    except Exception:
        pass
    if limit is not None:
        files = files[:limit]
    # Optionally deduplicate by dossier_seq parsed from ZBE segment
    dedup = os.getenv('PAM_DEDUP', '0') in ('1', 'true', 'True')
    results = []
    seen_dossiers = set()
    for f in files:
        print(f"Processing PAM example: {f.name}")
        try:
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = f.read_text(encoding="latin-1")
        except Exception as e:
            results.append({"file": f.name, "error": f"read_error: {e}"})
            continue

        # If dedup enabled, extract dossier_seq from first ZBE segment and skip if seen
        if dedup:
            dossier_seq = None
            try:
                for line in content.replace('\r', '\n').splitlines():
                    if line.startswith('ZBE'):
                        parts = line.split('|')
                        if len(parts) > 1 and parts[1]:
                            dossier_seq = parts[1].split('^')[0]
                        break
            except Exception:
                dossier_seq = None
            if dossier_seq and dossier_seq in seen_dossiers:
                print(f"[pam][dedup] skipping {f.name} (dossier_seq={dossier_seq})")
                continue
            if dossier_seq:
                seen_dossiers.add(dossier_seq)

        # Snapshot last MessageLog id
        last_id_row = session.exec(select(MessageLog.id).order_by(MessageLog.id.desc()).limit(1)).first()
        last_id = int(last_id_row) if last_id_row is not None else 0
        # Snapshot max ids for entities so we can detect newly created rows
        max_patient = session.exec(select(Patient.id).order_by(Patient.id.desc()).limit(1)).first() or 0
        max_dossier = session.exec(select(Dossier.id).order_by(Dossier.id.desc()).limit(1)).first() or 0
        max_venue = session.exec(select(Venue.id).order_by(Venue.id.desc()).limit(1)).first() or 0
        max_mouv = session.exec(select(Mouvement.id).order_by(Mouvement.id.desc()).limit(1)).first() or 0

        # Inbound validation
        try:
            inbound_val = validate_pam(content, direction="in")
            inbound_ok = inbound_val.level != "fail"
            inbound_issues = [i.__dict__ for i in inbound_val.issues]
        except Exception as e:
            inbound_ok = False
            inbound_issues = [{"error": str(e)}]

        # Process inbound via normal pipeline
        try:
            ack = asyncio.run(on_message_inbound_async(content, session, None))
        except Exception as e:
            results.append({"file": f.name, "error": str(e), "ack": None, "inbound_validation": {"ok": inbound_ok, "issues": inbound_issues}, "outbound_count": 0})
            continue

        # After processing, detect newly created entities and regenerate PAM HL7s for inspection
        try:
            new_patients = session.exec(select(Patient).where(Patient.id > max_patient)).all()
            new_dossiers = session.exec(select(Dossier).where(Dossier.id > max_dossier)).all()
            new_venues = session.exec(select(Venue).where(Venue.id > max_venue)).all()
            new_mouvs = session.exec(select(Mouvement).where(Mouvement.id > max_mouv)).all()
            # Write generated PAM HL7s into /tmp/medbridge_generated/pam
            base = ensure_out_dirs()
            pam_out = base / 'pam'
            import time, random
            for ent in (new_patients + new_dossiers + new_venues + new_mouvs):
                try:
                    # Determine entity type
                    if isinstance(ent, Patient):
                        et = 'patient'
                    elif isinstance(ent, Dossier):
                        et = 'dossier'
                    elif isinstance(ent, Venue):
                        et = 'venue'
                    elif isinstance(ent, Mouvement):
                        et = 'mouvement'
                    else:
                        et = 'unknown'
                    # Only generate when meaningful for PAM (patient/venue/mouvement)
                    if et not in ('patient', 'venue', 'mouvement'):
                        continue
                    try:
                        msg = generate_pam_hl7(ent, et, session)
                    except Exception:
                        msg = None
                    if not msg:
                        continue
                    suffix = f"{int(time.time())}-{random.randint(1000,9999)}"
                    fname = pam_out / f"gen_{et}_{getattr(ent,'id','unknown')}_{suffix}.hl7"
                    tmpf = fname.with_suffix(fname.suffix + '.tmp')
                    with tmpf.open('w', encoding='utf-8') as fh:
                        fh.write(msg)
                    tmpf.replace(fname)
                except Exception:
                    pass
        except Exception:
            pass

        created_logs = session.exec(select(MessageLog).where(MessageLog.id > last_id).order_by(MessageLog.id.asc())).all()
        outbound = [l for l in created_logs if (l.direction == "out") or (l.kind == "MLLP" and l.status in ("sent", "ack_ok", "pending"))]
        # Persist outbound MessageLog payloads to /tmp for manual inspection (unique filenames)
        try:
            base = ensure_out_dirs()
            pam_out = base / 'pam'
            import time, random
            for ob in outbound:
                try:
                    payload = ob.payload or ''
                    if not payload:
                        continue
                    # only write HL7-like payloads or those marked MLLP/FILE
                    if ob.kind in ('MLLP', 'FILE') or payload.startswith('MSH') or '\rPID' in payload:
                        suffix = f"{int(time.time())}-{random.randint(1000,9999)}"
                        fname = pam_out / f"out_{ob.id}_{suffix}.hl7"
                        tmpf = fname.with_suffix(fname.suffix + '.tmp')
                        with tmpf.open('w', encoding='utf-8') as fh:
                            fh.write(payload)
                        tmpf.replace(fname)
                except Exception:
                    pass
        except Exception:
            pass
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
            "inbound_validation": {"ok": inbound_ok, "issues": inbound_issues},
            "outbound_count": len(outbound),
            "outbound_ids": [o.id for o in outbound],
            "validations": val_results,
        })

    return results


def ensure_out_dirs():
    # Prefer an explicit env var, then a repo-local tmp/generated directory, then /tmp/medbridge_generated
    out_dir = os.getenv('MEDBRIDGE_OUT_DIR')
    if out_dir:
        base = Path(out_dir)
    else:
        # Use repository-local tmp/generated when available (convenient for CI/dev)
        try:
            repo_base = ROOT / 'tmp' / 'generated'
            repo_base.mkdir(parents=True, exist_ok=True)
            base = repo_base
        except Exception:
            base = Path('/tmp') / 'medbridge_generated'

    for sub in ("pam", "mfn", "fhir"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def main():
    # Ensure TESTING schema; optionally reset DB if requested
    if os.getenv("TESTING", "0") in ("1", "true", "True"):
        if os.getenv("RESET_DB", "0") in ("1", "true", "True"):
            try:
                print("RESET_DB=1: dropping and recreating all tables (testing mode)")
                SQLModel.metadata.drop_all(engine)
            except Exception:
                pass
        SQLModel.metadata.create_all(engine)

    with session_factory() as session:
        mfn_results = import_mfn_files(session)
        pam_results = run_pam_checks(session, limit=None)

    # Per-EntiteGeographique MFN generation checks: ensure generated MFN for a single EG
        eg_checks = []
        try:
            from app.models_structure import EntiteGeographique
            egs = session.exec(select(EntiteGeographique)).all()
            for eg in egs:
                try:
                    msg = generate_mfn_message(session, eg_identifier=getattr(eg, 'identifier', None), collapse_virtual=False)
                    # Count MFE entries for EG (M type) and total 'M' LOC markers
                    occurrences_m = msg.count('^^^^^M^^^^')
                    # Count distinct EG identifiers referenced in message (simple heuristic)
                    eg_id = getattr(eg, 'identifier', '')
                    contains_eg = eg_id and (eg_id in msg)

                    # Save full MFN message for inspection into /tmp
                    out_base = ensure_out_dirs()
                    mfn_out_dir = out_base / "mfn"
                    try:
                        import time, random
                        suffix = f"{int(time.time())}-{random.randint(1000,9999)}"
                        fname = mfn_out_dir / f"mfn_eg_{eg_id or 'unknown'}_{suffix}.hl7"
                        fname.write_text(msg, encoding='utf-8')
                    except Exception:
                        pass

                    eg_checks.append({
                        'eg_identifier': eg_id,
                        'mfe_m_count': occurrences_m,
                        'contains_eg': bool(contains_eg),
                        'sample_preview': msg.splitlines()[:10]
                    })
                except Exception as e:
                    eg_checks.append({'eg_identifier': getattr(eg, 'identifier', None), 'error': str(e)})
        except Exception as e:
            eg_checks = [{'error': f'Failed to run EG checks: {e}'}]

        out = {
            "mfn_imports": mfn_results,
            "pam_checks": pam_results,
            "pam_summary": {
                "total": len(pam_results),
                "with_outbound": sum(1 for r in pam_results if r.get("outbound_count", 0) > 0)
            }
        }
        out['eg_mfn_checks'] = eg_checks
        # Ensure generated out dirs in /tmp
        gen_base = ensure_out_dirs()

        # Save any generated MFN messages from eg_checks into files
        mfn_out_dir = gen_base / "mfn"
        for i, ck in enumerate(eg_checks):
            if 'sample_preview' in ck:
                try:
                    fname = mfn_out_dir / f"mfn_eg_{ck.get('eg_identifier') or i}.hl7"
                    # join sample preview lines
                    content = "\n".join(ck['sample_preview'])
                    fname.write_text(content, encoding='utf-8')
                except Exception:
                    pass

        # Save whole results JSON into /tmp for easier inspection
        out_dir = Path('/tmp')
        out_file = out_dir / "mfn_roundtrip_results.json"
        with out_file.open("w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
        print(f"Wrote roundtrip results to {out_file}")

        # Export FHIR bundles for each EntiteJuridique to tmp/generated/fhir/
        try:
            from app.models_structure import EntiteJuridique
            from app.services.fhir_export_service import FHIRExportService
            fhir_out_dir = gen_base / 'fhir'
            fhir_out_dir.mkdir(parents=True, exist_ok=True)
            base_url = os.getenv('FHIR_BASE_URL', 'http://example.org')
            fes = FHIRExportService(session, base_url=base_url, enable_cache=False)
            ejs = session.exec(select(EntiteJuridique)).all()
            # Debug: report how many EJ found and list identifiers
            try:
                ej_ids = [getattr(e, 'identifier', None) or getattr(e, 'id', None) for e in ejs]
                print(f"FHIR export: found {len(ejs)} EntiteJuridique entries: {ej_ids}")
            except Exception:
                print(f"FHIR export: found {len(ejs)} EntiteJuridique entries")
            for ej in ejs:
                try:
                    bundle = fes.export_structure(ej)
                    import time, random
                    suffix = f"{int(time.time())}-{random.randint(1000,9999)}"
                    fname = fhir_out_dir / f"fhir_ej_{ej.identifier or ej.id}_{suffix}.json"
                    fname.write_text(json.dumps(bundle.model_dump(), ensure_ascii=False, indent=2), encoding='utf-8')
                    print(f"Wrote FHIR bundle for EJ {ej.id} -> {fname}")
                except Exception as e:
                    print(f"Failed to export FHIR for EJ {ej.id}: {e}")
        except Exception as e:
            print(f"FHIR export skipped: {e}")

        # Also write a summary of generated outputs
        summary_file = gen_base / "summary.json"
        try:
            with summary_file.open('w', encoding='utf-8') as sf:
                sf.write(json.dumps({
                    'mfn_written_count': len(list((gen_base / 'mfn').glob('*.hl7'))),
                    'pam_written_count': len(list((gen_base / 'pam').glob('*.hl7'))),
                    'fhir_written_count': len(list((gen_base / 'fhir').glob('*.json'))),
                }, indent=2, ensure_ascii=False))
        except Exception:
            pass

        # Print a brief file summary for convenience
        try:
            print('\nGenerated files summary:')
            for sub in ('mfn', 'pam', 'fhir'):
                d = gen_base / sub
                files = sorted([str(p) for p in d.iterdir() if p.is_file()])
                print(f"  {sub}: {len(files)} files")
                for f in files[:10]:
                    print('    ', f)
                if len(files) > 10:
                    print('    ', '...')
        except Exception:
            pass


if __name__ == "__main__":
    main()
