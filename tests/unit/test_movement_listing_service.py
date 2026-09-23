from datetime import datetime, timedelta, timezone

import pytest

from app.models import Dossier, Mouvement, Patient, Venue
from app.services.movement_listing import MovementListContextError, load_movement_list


def _movement_context(session):
    patient = Patient(identifier="IPP-LIST-1", family="DUPONT", given="Alice")
    session.add(patient)
    session.flush()
    dossier = Dossier(
        dossier_seq=901,
        patient_id=patient.id,
        admit_time=datetime.now(timezone.utc),
    )
    session.add(dossier)
    session.flush()
    venue = Venue(
        venue_seq=901,
        dossier_id=dossier.id,
        start_time=datetime.now(timezone.utc),
    )
    session.add(venue)
    session.flush()
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Mouvement(
                mouvement_seq=901,
                venue_id=venue.id,
                type="ADT^A01",
                movement_type="admission",
                status="completed",
                location="Accueil",
                when=now - timedelta(hours=2),
            ),
            Mouvement(
                mouvement_seq=902,
                venue_id=venue.id,
                type="ADT^A02",
                movement_type="transfer",
                status="completed",
                location="Cardiologie",
                when=now - timedelta(hours=1),
            ),
            Mouvement(
                mouvement_seq=903,
                venue_id=venue.id,
                type="ADT^A11",
                movement_type="admission-cancel",
                status="cancelled",
                location="Accueil",
                when=now,
            ),
        ]
    )
    session.commit()
    return patient, dossier, venue


def test_movement_listing_filters_orders_and_loads_navigation_context(session):
    patient, dossier, venue = _movement_context(session)

    result = load_movement_list(
        session,
        venue_id=venue.id,
        dossier_id=None,
        ej_id=None,
        include_cancelled=False,
        order="desc",
        movement_type=None,
        status="completed",
        location_filter=None,
    )

    assert [movement.mouvement_seq for movement in result.movements] == [902, 901]
    assert result.venue.id == venue.id
    assert result.dossier.id == dossier.id
    assert result.dossier.patient.id == patient.id


def test_movement_listing_applies_type_and_location_filters(session):
    _patient, dossier, _venue = _movement_context(session)

    result = load_movement_list(
        session,
        venue_id=None,
        dossier_id=dossier.id,
        ej_id=None,
        include_cancelled=True,
        order="asc",
        movement_type="ADT^A02",
        status=None,
        location_filter="cardio",
    )

    assert [movement.mouvement_seq for movement in result.movements] == [902]


def test_movement_listing_reports_missing_context(session):
    with pytest.raises(MovementListContextError) as missing_parameter:
        load_movement_list(
            session,
            venue_id=None,
            dossier_id=None,
            ej_id=None,
            include_cancelled=False,
            order="asc",
            movement_type=None,
            status=None,
            location_filter=None,
        )
    assert missing_parameter.value.status_code == 400

    with pytest.raises(MovementListContextError) as missing_venue:
        load_movement_list(
            session,
            venue_id=999_999,
            dossier_id=None,
            ej_id=None,
            include_cancelled=False,
            order="asc",
            movement_type=None,
            status=None,
            location_filter=None,
        )
    assert missing_venue.value.status_code == 404


def test_movement_list_route_renders_the_loaded_context(client, session):
    _patient, _dossier, venue = _movement_context(session)

    response = client.get(f"/mouvements?venue_id={venue.id}")

    assert response.status_code == 200
    assert "Venue #901" in response.text
    assert "Cardiologie" in response.text
    assert "ADT^A11" not in response.text
