from sqlmodel import SQLModel, create_engine, Session
from datetime import datetime, timezone
import uuid

from app.models import Venue, Mouvement
from app.models_identifiers import Identifier, IdentifierType
from app.services.pam_sequence_validator import validate_pam_sequence


def _create_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_update_references_existing_mouvement():
    engine = _create_memory_db()
    with Session(engine) as session:
        # Create a patient and dossier required for Venue
        p = type("P", (), {})()
        from app.models import Patient, Dossier
        patient = Patient(family="DOE", given="JOHN")
        session.add(patient)
        session.flush()

        dossier = Dossier(dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
        session.add(dossier)
        session.flush()

        # Create a venue
        v = Venue(venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
        session.add(v)
        session.flush()

        # Create a movement and identifier
        m = Mouvement(mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, venue_id=v.id, when=datetime.now(timezone.utc), trigger_event="A01")
        session.add(m)
        session.flush()

        ident = Identifier(value=str(m.mouvement_seq), type=IdentifierType.MVT, system="SYS", mouvement_id=m.id)
        session.add(ident)
        session.commit()

        # Build a HL7 message with ZBE referencing the movement identifier
        msh = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A11|MSG001|P|2.5"
        pid = "PID|1|P123||DOE^JOHN||19700101"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||"
        # ZBE-1 as CX: value^ns^oid
        zbe = f"ZBE|{m.mouvement_seq}^^^SYS&1.2.3&ISO|202501010101||CANCEL|Y|A01||||"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"

        res = validate_pam_sequence(msg, session)
        assert res.is_valid


def test_update_references_cancelled_mouvement():
    engine = _create_memory_db()
    with Session(engine) as session:
        from app.models import Patient, Dossier
        patient = Patient(family="DOE", given="JANE")
        session.add(patient)
        session.flush()

        dossier = Dossier(dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
        session.add(dossier)
        session.flush()

        v = Venue(venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
        session.add(v)
        session.flush()

        m = Mouvement(mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, venue_id=v.id, when=datetime.now(timezone.utc), trigger_event="A01", status="cancelled")
        session.add(m)
        session.flush()

        ident = Identifier(value=str(m.mouvement_seq), type=IdentifierType.MVT, system="SYS", mouvement_id=m.id)
        session.add(ident)
        session.commit()

        msh = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A02|MSG002|P|2.5"
        pid = "PID|1|P124||SMITH^ANNE||19720101"
        pv1 = "PV1|1|I|WARD^102^B2^^O|3||||||||||||||||||||"
        zbe = f"ZBE|{m.mouvement_seq}^^^SYS&1.2.3&ISO|202501010101||UPDATE|N|A01||||"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"

        res = validate_pam_sequence(msg, session)
        codes = {i.code for i in res.issues}
        assert "ZBE_REF_ALREADY_CANCELLED" in codes
        assert not res.is_valid


def test_a01_a02_a03_sequence_allowed():
    engine = _create_memory_db()
    with Session(engine) as session:
        from app.models import Patient, Dossier
        patient = Patient(family="DOE", given="PAUL")
        session.add(patient)
        session.flush()

        dossier = Dossier(dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
        session.add(dossier)
        session.flush()

        v = Venue(venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
        session.add(v)
        session.flush()

        # Create initial A01 movement
        m1 = Mouvement(mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, venue_id=v.id, when=datetime.now(timezone.utc), trigger_event="A01")
        session.add(m1)
        session.flush()

        # A02 message referencing venue via PV1-19 should be allowed after A01
        msh = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A02|MSG003|P|2.5"
        pid = "PID|1|P125||BLAKE^TOM||19800101"
        # PV1-19 with venue_seq
        pv1_a02 = f"PV1|1|I|WARD^201^C1^^O|3|||||||||||||||||||||{v.venue_seq}"
        zbe_a02 = "ZBE|6001^^^SYS&1.2.3&ISO|202501010101||INSERT|N|A02||||"
        msg_a02 = "\r".join([msh, pid, pv1_a02, zbe_a02]) + "\r"
        res_a02 = validate_pam_sequence(msg_a02, session)
        assert res_a02.is_valid

        # Now simulate adding the A02 movement to DB
        m2 = Mouvement(mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000, venue_id=v.id, when=datetime.now(timezone.utc), trigger_event="A02")
        session.add(m2)
        session.flush()

        # A03 (discharge) should be allowed after A02
        msh3 = "MSH|^~\\&|S|F|R|F|202501010101||ADT^A03|MSG004|P|2.5"
        pv1_a03 = f"PV1|1|I|WARD^201^C1^^O|3|||||||||||||||||||||{v.venue_seq}"
        zbe_a03 = "ZBE|7001^^^SYS&1.2.3&ISO|202501010101||INSERT|N|A03||||"
        msg_a03 = "\r".join([msh3, pid, pv1_a03, zbe_a03]) + "\r"
        res_a03 = validate_pam_sequence(msg_a03, session)
        assert res_a03.is_valid
