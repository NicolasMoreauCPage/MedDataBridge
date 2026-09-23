from datetime import datetime

import pytest

from app.models import Dossier, Mouvement, Patient, Venue
from app.models_structure import Chambre, Lit, UniteFonctionnelle, UniteHebergement
from app.services.movement_details import MovementDetailsError, load_movement_details


def _detail_context(session):
    uf = UniteFonctionnelle(
        identifier="UF-DETAIL",
        name="Unité détail",
        short_name="UF détail",
    )
    session.add(uf)
    session.flush()
    uh = UniteHebergement(
        identifier="UH-DETAIL",
        name="Hébergement détail",
        unite_fonctionnelle_id=uf.id,
    )
    session.add(uh)
    session.flush()
    chambre = Chambre(
        identifier="CH-DETAIL",
        name="Chambre détail",
        unite_hebergement_id=uh.id,
    )
    session.add(chambre)
    session.flush()
    lit = Lit(identifier="LIT-DETAIL", name="Lit détail", chambre_id=chambre.id)
    session.add(lit)
    session.flush()
    patient = Patient(patient_seq=9701, family="DURAND", given="Sam")
    session.add(patient)
    session.flush()
    dossier = Dossier(
        dossier_seq=9701,
        patient_id=patient.id,
        admit_time=datetime(2026, 3, 1, 8, 0),
    )
    session.add(dossier)
    session.flush()
    venue = Venue(
        venue_seq=9701,
        dossier_id=dossier.id,
        start_time=dossier.admit_time,
    )
    session.add(venue)
    session.flush()
    movement = Mouvement(
        mouvement_seq=9701,
        venue_id=venue.id,
        type="ADT^A01",
        trigger_event="A01",
        movement_type="admission",
        when=venue.start_time,
        location="UH-DETAIL^CH-DETAIL^LIT-DETAIL",
        uf_responsabilite=uf.identifier,
        uf_soins_code=uf.identifier,
    )
    session.add(movement)
    session.commit()
    return movement


def test_movement_details_resolves_complete_location_and_uf_labels(session):
    movement = _detail_context(session)

    details = load_movement_details(session, movement.id)

    assert details.movement.id == movement.id
    assert details.movement.venue.dossier.patient.family == "DURAND"
    assert details.uf_responsable_label == "UF détail"
    assert details.uf_soins_label == "UF détail"
    assert details.uf_hebergement_label == "UF détail"
    assert details.chambre_info == "Chambre détail"
    assert details.lit_info == "Lit détail"


def test_movement_details_reports_unknown_movement(session):
    with pytest.raises(MovementDetailsError):
        load_movement_details(session, 999_999)


def test_movement_detail_route_uses_projection(client, session):
    movement = _detail_context(session)

    response = client.get(f"/mouvements/{movement.id}")

    assert response.status_code == 200
    assert "UF détail" in response.text
    assert "Chambre détail" in response.text
    assert "Lit détail" in response.text
