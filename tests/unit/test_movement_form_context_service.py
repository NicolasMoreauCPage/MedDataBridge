from datetime import datetime, timedelta

import pytest

from app.models import Dossier, Mouvement, Patient, Venue
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.movement_form_context import (
    MovementFormContextError,
    build_new_movement_form,
)


def _field(context, name):
    return next(field for field in context.fields if field["name"] == name)


def _movement_form_data(session):
    ej = EntiteJuridique(identifier="EJ-FORM", name="EJ formulaire")
    session.add(ej)
    session.flush()
    eg = EntiteGeographique(
        identifier="EG-FORM",
        name="Site formulaire",
        entite_juridique_id=ej.id,
    )
    session.add(eg)
    session.flush()
    pole = Pole(identifier="POLE-FORM", name="Pôle", entite_geo_id=eg.id)
    session.add(pole)
    session.flush()
    service = Service(identifier="SVC-FORM", name="Service", pole_id=pole.id)
    session.add(service)
    session.flush()
    uf = UniteFonctionnelle(
        identifier="UF-FORM",
        name="Unité formulaire",
        service_id=service.id,
    )
    session.add(uf)
    session.flush()
    uh = UniteHebergement(
        identifier="UH-FORM",
        name="Hébergement formulaire",
        unite_fonctionnelle_id=uf.id,
    )
    session.add(uh)
    session.flush()
    chambre = Chambre(
        identifier="CH-FORM",
        name="Chambre formulaire",
        unite_hebergement_id=uh.id,
    )
    session.add(chambre)
    session.flush()
    lit = Lit(identifier="LIT-FORM", name="Lit formulaire", chambre_id=chambre.id)
    session.add(lit)
    session.flush()

    patient = Patient(patient_seq=9901, family="DUPONT", given="Alice")
    session.add(patient)
    session.flush()
    dossier = Dossier(
        dossier_seq=9901,
        patient_id=patient.id,
        admit_time=datetime(2026, 1, 2, 8, 0),
        entite_juridique_id=ej.id,
        uf_responsabilite=uf.identifier,
    )
    session.add(dossier)
    session.flush()
    venue = Venue(
        venue_seq=9901,
        dossier_id=dossier.id,
        start_time=datetime(2026, 1, 2, 8, 0),
        uf_responsabilite=uf.identifier,
        uf_soins_code=uf.identifier,
        chambre_id=chambre.id,
        lit_id=lit.id,
    )
    session.add(venue)
    session.commit()
    return dossier, venue, uf, uh, chambre, lit


def test_new_movement_form_uses_submission_contracts_and_prefills_location(session):
    dossier, venue, uf, uh, chambre, lit = _movement_form_data(session)
    now = datetime(2026, 1, 2, 9, 30)

    context = build_new_movement_form(
        session,
        venue_id=venue.id,
        dossier_id=dossier.id,
        now=now,
    )

    assert context.title == "Nouveau mouvement pour le dossier #9901"
    assert _field(context, "when")["value"] == "2026-01-02T09:30"
    assert _field(context, "uf_id")["value"] == str(uf.id)
    assert _field(context, "uf_id")["options"] == [
        {"value": str(uf.id), "label": "Unité formulaire"}
    ]
    assert _field(context, "uf_soins_id")["value"] == "UF-FORM"
    assert _field(context, "uh_id")["value"] == str(uh.id)
    assert _field(context, "chambre_id")["value"] == str(chambre.id)
    assert _field(context, "lit_id")["value"] == str(lit.id)

    type_options = _field(context, "type")["options"]
    assert {option["value"] for option in type_options} == {"ADT^A01"}
    assert type_options[0]["requires_location"] is True


def test_new_movement_form_reuses_latest_movement_once_for_transition_and_date(session):
    dossier, venue, uf, _uh, _chambre, _lit = _movement_form_data(session)
    movement_time = datetime(2026, 1, 2, 10, 0)
    session.add(
        Mouvement(
            mouvement_seq=9901,
            venue_id=venue.id,
            type="ADT^A01",
            trigger_event="A01",
            when=movement_time,
            uf_responsabilite=uf.identifier,
            uf_soins_code=uf.identifier,
            location="UH-FORM^CH-FORM^LIT-FORM",
            from_location="Accueil",
            reason="programmee",
        )
    )
    session.commit()

    context = build_new_movement_form(
        session,
        venue_id=venue.id,
        dossier_id=dossier.id,
        now=movement_time + timedelta(hours=5),
    )

    assert _field(context, "when")["value"] == "2026-01-02T10:01"
    assert _field(context, "from_location")["value"] == "Accueil"
    assert _field(context, "reason")["value"] == "programmee"
    assert {option["value"] for option in _field(context, "type")["options"]} == {
        "ADT^A02",
        "ADT^A03",
        "ADT^A06",
        "ADT^A11",
        "ADT^A21",
    }


def test_new_movement_form_reports_empty_venue_scope(session):
    with pytest.raises(MovementFormContextError) as error:
        build_new_movement_form(
            session,
            venue_id=None,
            dossier_id=999_999,
        )

    assert error.value.status_code == 404
    assert error.value.back_url == "/venues/new"


def test_new_movement_route_renders_standard_event_values(client, session):
    dossier, venue, _uf, _uh, _chambre, _lit = _movement_form_data(session)

    response = client.get(
        f"/mouvements/new?dossier_id={dossier.id}&venue_id={venue.id}"
    )

    assert response.status_code == 200
    assert 'option value="ADT^A01"' in response.text
    assert 'option value="admission"' not in response.text
