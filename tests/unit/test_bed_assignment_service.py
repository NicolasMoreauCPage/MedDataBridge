from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.db import engine
from app.models import Dossier, Mouvement, Patient, Venue
from app.models_structure import Chambre, Lit
from app.services.bed_assignment import assign_patient_to_bed


def test_bed_assignment_batches_movement_history_and_creates_a02(session):
    patient = Patient(identifier="IPP-BED-1", family="MARTIN", given="Alice")
    room = Chambre(identifier="CH-BED-1", name="Chambre")
    session.add_all([patient, room])
    session.flush()
    bed = Lit(identifier="LIT-BED-1", name="Lit 1", chambre_id=room.id)
    dossier = Dossier(
        dossier_seq=701,
        patient_id=patient.id,
        admit_time=datetime.now(timezone.utc),
    )
    session.add_all([bed, dossier])
    session.flush()
    old_venue = Venue(
        venue_seq=701,
        dossier_id=dossier.id,
        start_time=datetime.now(timezone.utc) - timedelta(days=2),
    )
    active_venue = Venue(
        venue_seq=702,
        dossier_id=dossier.id,
        start_time=datetime.now(timezone.utc),
        assigned_location="Accueil",
    )
    session.add_all([old_venue, active_venue])
    session.flush()
    session.add(
        Mouvement(
            mouvement_seq=701,
            venue_id=old_venue.id,
            type="ADT^A03",
            trigger_event="A03",
            movement_type="discharge",
            when=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    session.commit()

    movement_history_selects = 0

    def count_movement_selects(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal movement_history_selects
        normalized = statement.lower()
        if "from mouvement" in normalized and "mouvement.venue_id in" in normalized:
            movement_history_selects += 1

    event.listen(engine, "before_cursor_execute", count_movement_selects)
    try:
        result = assign_patient_to_bed(
            session,
            bed_id=bed.id,
            patient_id=patient.id,
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_movement_selects)

    session.refresh(active_venue)
    assert active_venue.lit_id == bed.id
    assert active_venue.chambre_id == room.id
    assert result.movement is not None
    assert result.movement.trigger_event == "A02"
    assert result.movement.from_location == "Accueil"
    assert result.movement.to_location == "Lit 1"
    assert movement_history_selects == 1


def test_bed_assignment_is_idempotent_when_the_venue_already_occupies_the_bed(session):
    patient = Patient(identifier="IPP-BED-2", family="DURAND", given="Lou")
    room = Chambre(identifier="CH-BED-2", name="Chambre 2")
    session.add_all([patient, room])
    session.flush()
    bed = Lit(identifier="LIT-BED-2", name="Lit 2", chambre_id=room.id)
    dossier = Dossier(
        dossier_seq=702,
        patient_id=patient.id,
        admit_time=datetime.now(timezone.utc),
    )
    session.add_all([bed, dossier])
    session.flush()
    venue = Venue(
        venue_seq=703,
        dossier_id=dossier.id,
        start_time=datetime.now(timezone.utc),
        lit_id=bed.id,
        chambre_id=room.id,
    )
    session.add(venue)
    session.commit()

    result = assign_patient_to_bed(session, bed_id=bed.id, patient_id=patient.id)

    assert result.movement is None
    assert result.message == "Le patient occupe déjà ce lit."
