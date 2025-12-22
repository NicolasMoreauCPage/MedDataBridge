from datetime import datetime
import uuid
from sqlmodel import Session
from app.db import engine, init_db
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.services.hl7_generator import generate_admission_message, generate_transfer_message
from app.services.hl7_generator import generate_adt_message


def _setup(session: Session):
    # Use UUID-based identifiers to avoid conflicts
    dossier_seq = int(uuid.uuid4().hex[:8], 16) % 1000000  # Generate unique seq number
    venue_seq = int(uuid.uuid4().hex[:8], 16) % 1000000    # Generate unique seq number

    patient = Patient(family="ZBE", given="Test", birth_date="1980-01-01", gender="male")
    session.add(patient); session.commit(); session.refresh(patient)
    dossier = Dossier(dossier_seq=dossier_seq, patient_id=patient.id, uf_responsabilite="UF-INIT", admit_time=datetime.utcnow(), dossier_type=DossierType.HOSPITALISE)
    session.add(dossier); session.commit(); session.refresh(dossier)
    venue = Venue(venue_seq=venue_seq, dossier_id=dossier.id, uf_responsabilite="UF-INIT", start_time=datetime.utcnow(), code="LOC-INIT", label="Location Init")
    session.add(venue); session.commit(); session.refresh(venue)
    return patient, dossier, venue


def test_zbe_insert_generation():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        mouvement_seq = int(uuid.uuid4().hex[:8], 16) % 1000000  # Generate unique seq number
        mouvement = Mouvement(mouvement_seq=mouvement_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-INIT/BOX", trigger_event="A01", action="INSERT")
        session.add(mouvement); session.commit(); session.refresh(mouvement)
        msg = generate_admission_message(patient, dossier, venue, mouvement, session=session)
        assert "ZBE|" in msg
        assert "|INSERT|" in msg  # ZBE-4
        assert "|Y|" not in msg  # Historic not set


def test_zbe_transfer_pv1_previous_uf():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        # First movement admission sets UF INIT
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-INIT/BOX", trigger_event="A01", action="INSERT", uf_medicale_code="UF-INIT")
        session.add(m1); session.commit(); session.refresh(m1)
        # Second movement transfer A02 should include previous UF in PV1-6
        m2_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m2 = Mouvement(mouvement_seq=m2_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-NEW/BOX", trigger_event="A02", action="INSERT", uf_medicale_code="UF-NEW")
        session.add(m2); session.commit(); session.refresh(m2)
        msg = generate_transfer_message(patient, dossier, venue, m2, session=session)
        pv1 = next(s for s in msg.split("\r") if s.startswith("PV1"))
        parts = pv1.split("|")
        # PV1-6 index = 6 (0-based segment name); ensure previous UF present
        assert parts[6].endswith("UF-INIT"), f"PV1-6 should contain previous UF, got: {parts[6]}"


def test_zbe_update_requires_original_trigger():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A01", action="INSERT")
        session.add(m1); session.commit(); session.refresh(m1)
        # Create update movement referencing original A01
        m1.action = "UPDATE"
        m1.original_trigger = "A01"
        session.add(m1); session.commit();
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        assert "|UPDATE|" in zbe
        assert "|A01|" in zbe  # original trigger appears in ZBE-6


def test_zbe_cancel_action_generates_cancel_segment():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A01", action="INSERT")
        session.add(m1); session.commit(); session.refresh(m1)
        m1.action = "CANCEL"; m1.original_trigger = "A01"
        session.add(m1); session.commit(); session.refresh(m1)
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        assert "|CANCEL|" in zbe


def test_zbe_update_missing_original_trigger_should_fallback():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A01", action="INSERT")
        session.add(m1); session.commit(); session.refresh(m1)
        m1.action = "UPDATE"  # no original_trigger provided
        session.add(m1); session.commit(); session.refresh(m1)
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        # Solution de repli uses movement.trigger_event for ZBE-6
        assert "|A01|" in zbe


def test_zbe_historic_flag_Y():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        past_time = datetime.utcnow()
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=past_time, location="LOC-P/BOX", trigger_event="A01", action="INSERT", is_historic=True)
        session.add(m1); session.commit(); session.refresh(m1)
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        # ZBE-5 historic flag should be Y
        parts = zbe.split("|")
        assert parts[5] == "Y"


def test_zbe_warning_missing_uf_soins_optional():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A01", action="INSERT", uf_medicale_code="UF-MED")
        session.add(m1); session.commit(); session.refresh(m1)
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        # ZBE has no UF soins -> ZBE-8 empty
        parts = zbe.split("|")
        assert parts[8] == ""


def test_zbe_invalid_action_fallback_to_insert():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A01", action="BADACTION")
        session.add(m1); session.commit(); session.refresh(m1)
        # Generator should Solution de repli action to INSERT
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        assert "|INSERT|" in zbe


def test_zbe_update_missing_original_trigger_includes_fallback():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A02", action="UPDATE")
        session.add(m1); session.commit(); session.refresh(m1)
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        # Solution de repli original trigger uses movement.trigger_event
        parts = zbe.split("|")
        assert parts[6] == "A02"


def test_zbe_invalid_nature_code_not_emitted():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = _setup(session)
        # Provide an invalid nature value directly on movement
        m1_seq = int(uuid.uuid4().hex[:8], 16) % 1000000
        m1 = Mouvement(mouvement_seq=m1_seq, venue_id=venue.id, when=datetime.utcnow(), location="LOC-X/BOX", trigger_event="A01", action="INSERT", nature="ZZ")
        session.add(m1); session.commit(); session.refresh(m1)
        msg = generate_admission_message(patient, dossier, venue, m1, session=session)
        zbe = next(s for s in msg.split("\r") if s.startswith("ZBE"))
        parts = zbe.split("|")
        # derive_nature should ignore invalid override and compute from trigger (A01 => probably 'S' or mapped value). Ensure not 'ZZ'.
        assert parts[9] != "ZZ"

