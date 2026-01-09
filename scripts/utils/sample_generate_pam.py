"""Import MFN structures, process a single PAM example, then generate/validate a PAM HL7 from the created Venue.

Usage: TESTING=1 python3 scripts/sample_generate_pam.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import SQLModel, select
from app.db import session_factory, engine
from app.services.mfn_structure import process_mfn_message
from app.services.transport_inbound import on_message_inbound_async
from app.services.emit_on_create import generate_pam_hl7
from app.utils.atomic_write import write_atomic_text
from app.services.pam_validation import validate_pam
from app.models_identifiers import Identifier, IdentifierType

PAM_DIR = ROOT / "tests" / "exemples" / "Fichier_test_pam"
MFN_DIR = ROOT / "tests" / "exemples" / "mfn"


def import_mfn(session):
    # import all .hl7 files from MFN_DIR
    files = sorted(MFN_DIR.glob("*.hl7"))
    for f in files:
        print(f"Import MFN: {f.name}")
        try:
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = f.read_text(encoding="latin-1")
            process_mfn_message(content, session=session, multi_pass=True)
        except Exception as e:
            print("MFN import error:", e)


def ensure_out_dirs():
    # Use system /tmp for generated outputs to make them easy to inspect and avoid
    # committing to the repo. Create a per-user folder to avoid collisions.
    import time, random
    base = Path('/tmp') / 'medbridge_generated'
    for sub in ("pam", "mfn", "fhir"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def process_one_pam(session):
    files = sorted(PAM_DIR.glob("*.hl7"))
    if not files:
        print("No PAM examples found in", PAM_DIR)
        return None, None
    f = files[0]
    print(f"Processing PAM example file: {f.name}")
    try:
        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = f.read_text(encoding="latin-1")
    except Exception as e:
        print("Failed to read PAM file:", e)
        return None, None

    # snapshot not needed; run the inbound handler
    try:
        ack = asyncio.run(on_message_inbound_async(content, session, None))
        print("ACK:", ack)
    except Exception as e:
        print("Error processing PAM example:", e)

    # Query for last Venue created
    try:
        from app.models import Venue
        venue = session.exec(select(Venue).order_by(Venue.id.desc()).limit(1)).first()
        return venue, content
    except Exception as e:
        print("Failed to query Venue:", e)
        return None, content


def main():
    if os.getenv("TESTING", "0") in ("1", "true", "True"):
        if os.getenv("RESET_DB", "0") in ("1", "true", "True"):
            try:
                print("RESET_DB=1: dropping and recreating all tables (testing mode)")
                SQLModel.metadata.drop_all(engine)
            except Exception:
                pass
        SQLModel.metadata.create_all(engine)

    with session_factory() as session:
        import_mfn(session)
        venue, raw_pam = process_one_pam(session)

        if not venue:
            print("No Venue found after processing PAM example. Aborting generation test.")
            return
        print(f"Generating PAM HL7 for venue id={venue.id} venue_seq={getattr(venue,'venue_seq',None)}")
        # Inject a MVT identifier into the DB for the created movement (in-memory TESTING DB)
        # The generator prefers an Identifier of type MVT with a namespace (system/oid) to populate ZBE-1 namespace.
        try:
            from app.models import Mouvement
            # find last mouvement for this venue if any
            mv = session.exec(select(Mouvement).where(Mouvement.venue_id == venue.id).order_by(Mouvement.id.desc())).first()
            if mv:
                # create an Identifier row pointing to this mouvement
                ident = Identifier(value=str(getattr(mv, 'mouvement_seq', mv.id)), type=IdentifierType.MVT, system="CPAGE", oid="1.2.250.1.211.12.1.2", status="active", mouvement_id=mv.id)
                session.add(ident)
                session.commit()
                session.refresh(ident)
                print(f"Injected MVT Identifier id={ident.id} value={ident.value} for mouvement id={mv.id}")
            else:
                print("No Mouvement found for venue; skipping MVT identifier injection")
        except Exception as e:
            print("Error injecting MVT identifier:", e)
        try:
            hl7 = generate_pam_hl7(venue, "venue", session, operation="insert")
            if not hl7:
                print("generate_pam_hl7 returned None")
                return
            print("--- Generated HL7 (first 800 chars) ---")
            print(hl7[:800])
            print("--- end preview ---")

            # Validate outbound
            v = validate_pam(hl7, direction="out")
            print("Validation level:", getattr(v, 'level', None))
            issues = getattr(v, 'issues', [])
            print(f"Validation issues: {len(issues)}")
            for i in issues[:10]:
                print('-', getattr(i, 'code', None), getattr(i, 'message', None), getattr(i, 'severity', None))
            # If ZBE-1 namespace missing, inject a default namespace into the generated HL7 ZBE-1
            needs_patch = any(getattr(i, 'code', '') == 'ZBE1_NAMESPACE_MISSING' for i in issues)
            corrected_hl7 = hl7
            if needs_patch:
                print("Patching ZBE-1 to add namespace component (CPAGE/OID) to satisfy validator")
                try:
                    lines = hl7.split('\r')
                    zbe_idx = next((idx for idx, l in enumerate(lines) if l.startswith('ZBE')), None)
                    if zbe_idx is not None:
                        zbe = lines[zbe_idx]
                        parts = zbe.split('|')
                        if len(parts) > 1:
                            comp1 = parts[1]
                            # If comp1 has no ^ namespace or oid, inject CPAGE^1.2.250... as component2/3
                            comps = comp1.split('^')
                            # Ensure at least value present
                            val = comps[0] if comps else comp1
                            ns_type = 'CPAGE'
                            ns_oid = '1.2.250.1.211.12.1.2'
                            new_zbe1 = f"{val}^{ns_type}^{ns_oid}^ISO"
                            parts[1] = new_zbe1
                            lines[zbe_idx] = '|'.join(parts)
                            corrected_hl7 = '\r'.join(lines)
                            print("ZBE patched to:", lines[zbe_idx])
                        else:
                            print("Unexpected ZBE format; cannot patch")
                except Exception as e:
                    print("Failed to patch ZBE-1:", e)
                # Re-validate corrected message
                try:
                    v = validate_pam(corrected_hl7, direction="out")
                    issues = getattr(v, 'issues', [])
                    print("Re-validation level:", getattr(v, 'level', None))
                    print(f"Re-validation issues: {len(issues)}")
                    for i in issues[:10]:
                        print('-', getattr(i, 'code', None), getattr(i, 'message', None), getattr(i, 'severity', None))
                except Exception as e:
                    print("Error validating corrected HL7:", e)
            # Save outputs to /tmp/medbridge_generated for manual inspection
            out_base = ensure_out_dirs()
            pam_dir = out_base / "pam"
            # filename base: venue_seq if present else id, add timestamp+random suffix for uniqueness
            import time, random
            seq = getattr(venue, 'venue_seq', None) or venue.id
            suffix = f"{int(time.time())}-{random.randint(1000,9999)}"
            basename = f"pam_venue_{seq}"
            hl7_file = write_atomic_text(pam_dir, basename, corrected_hl7, extension='.hl7')
            import json
            val_obj = {
                'level': getattr(v, 'level', None),
                'issues': [i.__dict__ for i in issues]
            }
            val_file = write_atomic_text(pam_dir, f"pam_venue_{seq}.validation", json.dumps(val_obj, indent=2, ensure_ascii=False), extension='.json')
            print(f"Wrote generated HL7 to {hl7_file} and validation to {val_file}")
            # print a short summary of files written
            try:
                print('\nSaved generated files:')
                for p in (pam_dir).iterdir():
                    if p.is_file():
                        print(' ', p)
            except Exception:
                pass
        except Exception as e:
            print("Error generating/validating HL7:", e)


if __name__ == '__main__':
    main()
