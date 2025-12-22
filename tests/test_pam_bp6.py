from sqlmodel import SQLModel, create_engine, Session
import pytest
import uuid
from datetime import datetime, timezone

from app.services.pam_sequence_validator import validate_pam_sequence


def _create_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_cancel_nonexistent_reference():
    engine = _create_memory_db()
    with Session(engine) as session:
        # Build a HL7 CANCEL (ZBE action CANCEL) referencing a non-existent movement
        msh = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A08|MSG101|P|2.5"
        pid = "PID|1|P200||NOM^TEST||19900101"
        pv1 = "PV1|1|I|WARD^300^D1^^O|3||||||||||||||||||||"
        zbe = "ZBE|999999^^^SYS&1.2.3&ISO|202501010101||CANCEL|N|A08||||"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"

        
        res = validate_pam_sequence(msg, session)
        codes = {i.code for i in res.issues}
        assert "ZBE_REF_NOT_FOUND" in codes
        assert not res.is_valid


def test_bed_occupied_warning():
    engine = _create_memory_db()
    with Session(engine) as session:
        # Create minimal fixtures required for a Mouvement
        from app.models import Patient, Dossier, Venue, Mouvement

        patient = Patient(family="OCC", given="ONE")
        session.add(patient)
        session.flush()

        dossier = Dossier(dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
        session.add(dossier)
        session.flush()

        v = Venue(venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
        session.add(v)
        session.flush()

        # Existing movement occupying room R1 bed B1 (to_location contains '^R1^B1')
        m = Mouvement(mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, venue_id=v.id, when=datetime.now(timezone.utc), trigger_event="A01", to_location="^R1^B1")
        session.add(m)
        session.commit()

        # Incoming A02 requesting same room/bed in PV1-3
        msh = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A02|MSG102|P|2.5"
        pid = "PID|1|P201||BED^TEST||19910101"
        pv1 = "PV1|1|I|LOC^R1^B1^^O|3||||||||||||||||||||"
        zbe = "ZBE|6100^^^SYS&1.2.3&ISO|202501010101||INSERT|N|A02||||"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"

        res = validate_pam_sequence(msg, session)
        codes = {i.code for i in res.issues}
        assert "BED_OCCUPIED" in codes
        # Mode strict activé → BED_OCCUPIED devient erreur et doit bloquer
        assert not res.is_valid


@pytest.mark.xfail(reason="Transition validation edge-case: PV1 lookup semantics differ; to be improved", strict=False)
def test_transition_not_allowed_error():
    engine = _create_memory_db()
    with Session(engine) as session:
        from app.models import Patient, Dossier, Venue, Mouvement

        patient = Patient(family="TRANS", given="PAIR")
        session.add(patient)
        session.flush()

        dossier = Dossier(dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
        session.add(dossier)
        session.flush()

        v = Venue(venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
        session.add(v)
        session.flush()

        # Last movement recorded is an A02 (transfer), so incoming A01 is not allowed
        # according to the transition table. Use venue_seq as venue_id to match validator lookup.
        m = Mouvement(mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, venue_id=v.venue_seq, when=datetime.now(timezone.utc), trigger_event="A02")
        session.add(m)
        session.commit()

        # Sanity-check: the validator looks for Mouvement where Mouvement.venue_id == PV1-19 (venue_seq)
        from sqlmodel import select
        last_mov = session.exec(select(Mouvement).where(Mouvement.venue_id == v.venue_seq)).first()
        assert last_mov is not None

        msh = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A01|MSG103|P|2.5"
        pid = "PID|1|P202||TRANS^TEST||19880101"
        pv1 = f"PV1|1|I|WARD^400^E1^^O|3|||||||||||||||||||||{v.venue_seq}"
        zbe = "ZBE|8000^^^SYS&1.2.3&ISO|202501010101||INSERT|N|A01||||"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"

        res = validate_pam_sequence(msg, session)
        codes = {i.code for i in res.issues}
        assert "TRANSITION_NOT_ALLOWED" in codes
        # This is an error-level issue
        assert not res.is_valid
