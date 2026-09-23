from datetime import datetime

import pytest

from app.models import Dossier, Mouvement, Patient, Venue
from app.services.movement_deletion import (
    MovementDeletionError,
    delete_patient_movement,
)


def _movement(session):
    patient = Patient(patient_seq=9601, family="BERNARD", given="Lou")
    session.add(patient)
    session.flush()
    dossier = Dossier(
        dossier_seq=9601,
        patient_id=patient.id,
        admit_time=datetime(2026, 4, 1, 8, 0),
    )
    session.add(dossier)
    session.flush()
    venue = Venue(
        venue_seq=9601,
        dossier_id=dossier.id,
        start_time=dossier.admit_time,
    )
    session.add(venue)
    session.flush()
    movement = Mouvement(
        mouvement_seq=9601,
        venue_id=venue.id,
        type="ADT^A01",
        when=venue.start_time,
    )
    session.add(movement)
    session.commit()
    return movement, venue


def test_delete_patient_movement_notifies_with_loaded_context(session):
    movement, venue = _movement(session)
    notified = []

    venue_id = delete_patient_movement(
        session,
        movement_id=movement.id,
        before_delete=lambda item: notified.append(
            (item.id, item.venue.dossier.patient.family)
        ),
    )

    assert venue_id == venue.id
    assert notified == [(movement.id, "BERNARD")]
    assert session.get(Mouvement, movement.id) is None


def test_delete_patient_movement_does_not_notify_when_missing(session):
    notified = []

    with pytest.raises(MovementDeletionError):
        delete_patient_movement(
            session,
            movement_id=999_999,
            before_delete=notified.append,
        )

    assert notified == []
