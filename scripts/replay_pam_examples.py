"""Replay HL7 examples into an in-memory DB to build historical context.
This script performs minimal persistence of Patient/Dossier/Venue/Mouvement
from HL7 messages to allow sequence validation across messages.
"""
from sqlmodel import SQLModel, create_engine, Session, select
from pathlib import Path
from datetime import datetime, timezone
import re

from app.services.pam_validation import validate_pam
from app.services.pam_sequence_validator import validate_pam_sequence
from app.services.mllp import parse_msh_fields
from app.services.pam import _parse_zbe_segment
from app.db import get_next_sequence

EXAMPLES_DIR = Path("tests/exemples/Fichier_test_pam")


def _create_memory_db():
    engine = create_engine("sqlite:///:memory:")
    # Ensure all models are imported
    import app.models  # noqa: F401
    import app.models_identifiers  # noqa: F401
    SQLModel.metadata.create_all(engine)
    return engine


def parse_pid(msg: str):
    lines = [l for l in re.split(r"\r|\n", msg) if l.strip()]
    pid = next((l for l in lines if l.startswith("PID")), None)
    if not pid:
        return None
    parts = pid.split("|")
    pid3 = parts[3] if len(parts) > 3 else ""
    pid5 = parts[5] if len(parts) > 5 else ""
    identifier = pid3.split("~")[0].split("^")[0] if pid3 else None
    family = pid5.split("^")[0] if pid5 else None
    given = pid5.split("^")[1] if pid5 and "^" in pid5 else None
    return {"identifier": identifier, "family": family, "given": given}


def parse_pv1(msg: str):
    lines = [l for l in re.split(r"\r|\n", msg) if l.strip()]
    pv1 = next((l for l in lines if l.startswith("PV1")), None)
    if not pv1:
        return None
    parts = pv1.split("|")
    pv1_3 = parts[3] if len(parts) > 3 else ""
    pv1_19 = parts[19] if len(parts) > 19 else ""
    return {"loc": pv1_3, "venue_seq": pv1_19}


def replay(limit=None):
    engine = _create_memory_db()
    files = sorted(EXAMPLES_DIR.glob("*.hl7"))
    if limit:
        files = files[:limit]
    created = 0
    with Session(engine) as session:
        for f in files:
            msg = f.read_text(errors="replace")
            stateless = validate_pam(msg)
            seq = validate_pam_sequence(msg, session)
            # If sequence validation fails, skip persistence (strict mode)
            if seq.level == "fail":
                print(f"SKIP (seq fail): {f}")
                continue
            # Minimal persistence: create patient/dossier/venue/mouvement if INSERT
            msh = parse_msh_fields(msg)
            trigger = msh.get("trigger")
            pid = parse_pid(msg)
            pv1 = parse_pv1(msg)
            zbe = _parse_zbe_segment(msg)

            # Create or find Patient
            from app.models import Patient, Dossier, Venue, Mouvement
            from app.models_identifiers import Identifier, IdentifierType
            if pid and pid.get("identifier"):
                patient = session.exec(select(Patient).where(Patient.identifier == pid["identifier"])).first()
                if not patient:
                        patient = Patient(family=pid.get("family") or "UNK", given=pid.get("given") or "UNK", identifier=pid.get("identifier"))
                        session.add(patient)
                        session.commit()
                        session.refresh(patient)
            else:
                # fallback: create anonymous patient
                patient = Patient(family="UNK", given="UNK")
                session.add(patient)
                session.commit()
                session.refresh(patient)

            # Create Dossier for patient if none
            dossier = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
            if not dossier:
                dossier = Dossier(dossier_seq=get_next_sequence(session, "dossier"), patient_id=patient.id, admit_time=datetime.now(timezone.utc))
                session.add(dossier)
                session.commit()
                session.refresh(dossier)

            # Venue: prefer PV1-19 numeric
            venue = None
            if pv1 and pv1.get("venue_seq"):
                try:
                    venue_seq = int(pv1["venue_seq"].split("^")[0])
                except Exception:
                    venue_seq = None
                if venue_seq:
                    venue = session.exec(select(Venue).where(Venue.venue_seq == venue_seq)).first()
                    if not venue:
                        venue = Venue(venue_seq=venue_seq, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
                        session.add(venue)
                        session.commit()
                        session.refresh(venue)

            if not venue:
                # create a new venue
                venue = Venue(venue_seq=get_next_sequence(session, "venue"), dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
                session.add(venue)
                session.commit()
                session.refresh(venue)

            # Create Mouvement for INSERT actions or when action_type missing
            if not zbe or (zbe and zbe.get("action_type") in (None, "INSERT")):
                mseq = None
                if zbe and zbe.get("movement_id"):
                    try:
                        mseq = int(zbe.get("movement_id"))
                    except Exception:
                        mseq = get_next_sequence(session, "mouvement")
                else:
                    mseq = get_next_sequence(session, "mouvement")
                # If a mouvement with same sequence already exists, skip creation
                existing_mv = session.exec(select(Mouvement).where(Mouvement.mouvement_seq == mseq)).first()
                if existing_mv:
                    created += 0
                    continue
                mv = Mouvement(mouvement_seq=mseq, venue_id=venue.id, when=datetime.now(timezone.utc), trigger_event=trigger)
                # store to_location from PV1-3 if present
                if pv1 and pv1.get("loc"):
                    mv.to_location = pv1.get("loc")
                # ZBE action
                if zbe and zbe.get("action_type"):
                    mv.action = zbe.get("action_type")
                session.add(mv)
                session.commit()
                session.refresh(mv)
                # Add identifier if ZBE-1 present
                if zbe and zbe.get("movement_id"):
                    try:
                        ident_val = zbe.get("movement_id")
                        ident = Identifier(value=ident_val.split("^")[0], type=IdentifierType.MVT, system="HL7", mouvement_id=mv.id)
                        session.add(ident)
                        session.commit()
                    except Exception:
                        pass
                created += 1
    print(f"Replayed {len(files)} files, created {created} mouvements.")


if __name__ == '__main__':
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    replay(limit=lim)
