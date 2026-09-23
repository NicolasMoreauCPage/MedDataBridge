from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models import Dossier, Mouvement, Patient, Venue
from app.models_structure import Chambre, Lit, UniteFonctionnelle, UniteHebergement
from app.services.movement_creation import (
    MovementCreationError,
    create_patient_movement,
)


def _creation_context(session):
    uf = UniteFonctionnelle(identifier="UF-CREATE", name="UF création")
    other_uf = UniteFonctionnelle(identifier="UF-OTHER", name="Autre UF")
    session.add_all([uf, other_uf])
    session.flush()
    uh = UniteHebergement(
        identifier="UH-CREATE",
        name="UH création",
        unite_fonctionnelle_id=uf.id,
    )
    other_uh = UniteHebergement(
        identifier="UH-OTHER",
        name="Autre UH",
        unite_fonctionnelle_id=other_uf.id,
    )
    session.add_all([uh, other_uh])
    session.flush()
    chambre = Chambre(
        identifier="CH-CREATE",
        name="Chambre création",
        unite_hebergement_id=uh.id,
    )
    other_chambre = Chambre(
        identifier="CH-OTHER",
        name="Autre chambre",
        unite_hebergement_id=other_uh.id,
    )
    session.add_all([chambre, other_chambre])
    session.flush()
    lit = Lit(identifier="LIT-CREATE", name="Lit création", chambre_id=chambre.id)
    session.add(lit)
    session.flush()
    patient = Patient(patient_seq=9801, family="MARTIN", given="Lina")
    session.add(patient)
    session.flush()
    venue_start = datetime(2026, 2, 1, 8, 0)
    dossier = Dossier(
        dossier_seq=9801,
        patient_id=patient.id,
        admit_time=venue_start,
    )
    session.add(dossier)
    session.flush()
    venue = Venue(
        venue_seq=9801,
        dossier_id=dossier.id,
        start_time=venue_start,
    )
    session.add(venue)
    session.commit()
    return venue, uf, uh, chambre, other_chambre, lit


def test_create_patient_movement_persists_location_and_updates_venue(session):
    venue, uf, uh, chambre, _other_chambre, lit = _creation_context(session)

    movement = create_patient_movement(
        session,
        venue_id=venue.id,
        type_code="ADT^A01",
        when=venue.start_time + timedelta(minutes=5),
        uf_id=uf.id,
        uf_soins_identifier=uf.identifier,
        uh_id=uh.id,
        chambre_id=chambre.id,
        lit_id=lit.id,
        reason="programmee",
    )

    assert movement.type == "ADT^A01"
    assert movement.trigger_event == "A01"
    assert movement.movement_type == "admission"
    assert movement.location == "UH-CREATE^CH-CREATE^LIT-CREATE"
    assert movement.to_location == movement.location
    assert movement.uf_responsabilite == "UF-CREATE"
    assert movement.uf_soins_code == "UF-CREATE"
    session.refresh(venue)
    assert venue.chambre_id == chambre.id
    assert venue.lit_id == lit.id
    assert venue.assigned_location == movement.location


def test_create_patient_transfer_uses_latest_location_as_origin(session):
    venue, uf, uh, chambre, _other_chambre, lit = _creation_context(session)
    admission = create_patient_movement(
        session,
        venue_id=venue.id,
        type_code="ADT^A01",
        when=venue.start_time + timedelta(minutes=5),
        uh_id=uh.id,
    )

    transfer = create_patient_movement(
        session,
        venue_id=venue.id,
        type_code="ADT^A02",
        when=admission.when + timedelta(minutes=5),
        uf_id=uf.id,
        uh_id=uh.id,
        chambre_id=chambre.id,
        lit_id=lit.id,
    )

    assert transfer.from_location == "UH-CREATE"
    assert transfer.location == "UH-CREATE^CH-CREATE^LIT-CREATE"


def test_create_patient_movement_rejects_invalid_hierarchy_without_writing(session):
    venue, _uf, uh, _chambre, other_chambre, lit = _creation_context(session)

    with pytest.raises(MovementCreationError, match="n'appartient pas"):
        create_patient_movement(
            session,
            venue_id=venue.id,
            type_code="ADT^A01",
            when=venue.start_time + timedelta(minutes=5),
            uh_id=uh.id,
            chambre_id=other_chambre.id,
            lit_id=lit.id,
        )

    assert session.exec(select(Mouvement)).all() == []


def test_create_patient_movement_rejects_invalid_type_and_chronology(session):
    venue, _uf, uh, _chambre, _other_chambre, _lit = _creation_context(session)

    with pytest.raises(MovementCreationError, match="ADT valide"):
        create_patient_movement(
            session,
            venue_id=venue.id,
            type_code="admission",
            when=venue.start_time,
            uh_id=uh.id,
        )
    with pytest.raises(MovementCreationError, match="début de la venue"):
        create_patient_movement(
            session,
            venue_id=venue.id,
            type_code="ADT^A01",
            when=venue.start_time - timedelta(minutes=1),
            uh_id=uh.id,
        )
