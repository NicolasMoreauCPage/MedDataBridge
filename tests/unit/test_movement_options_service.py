import pytest

from app.models_structure import Chambre, Lit, UniteFonctionnelle, UniteHebergement
from app.services import movement_options
from app.services.movement_options import (
    MovementOptionParentNotFound,
    accommodation_options,
    bed_options,
    movement_reason_options,
    room_options,
)


def _structure(session):
    uf = UniteFonctionnelle(identifier="UF-OPTIONS", name="UF options")
    session.add(uf)
    session.flush()
    uh = UniteHebergement(
        identifier="UH-OPTIONS",
        name="UH options",
        unite_fonctionnelle_id=uf.id,
    )
    session.add(uh)
    session.flush()
    room = Chambre(
        identifier="CH-OPTIONS",
        name="Chambre options",
        unite_hebergement_id=uh.id,
    )
    session.add(room)
    session.flush()
    bed = Lit(identifier="LIT-OPTIONS", name="Lit options", chambre_id=room.id)
    session.add(bed)
    session.commit()
    return uf, uh, room, bed


def test_dependent_movement_options_return_stable_contracts(session):
    uf, uh, room, bed = _structure(session)

    assert accommodation_options(session, uf.identifier) == [
        {"value": str(uh.id), "label": "UH options"}
    ]
    assert room_options(session, uh.id) == [
        {"value": str(room.id), "label": "Chambre options"}
    ]
    assert bed_options(session, room.id) == [
        {"value": str(bed.id), "label": "Lit options"}
    ]


def test_accommodation_options_reports_unknown_uf(session):
    with pytest.raises(MovementOptionParentNotFound):
        accommodation_options(session, "UF-UNKNOWN")


def test_reason_options_extract_event_from_full_adt_code(monkeypatch):
    options = [
        {"value": "urgence", "label": "Urgence"},
        {"value": "programmee", "label": "Programmée"},
        {"value": "guerison", "label": "Guérison"},
    ]
    monkeypatch.setattr(
        movement_options,
        "get_vocabulary_options",
        lambda _name: options,
    )

    assert movement_reason_options("ADT^A01") == options[:2]
    assert movement_reason_options("A03") == options[2:]
    assert movement_reason_options("ADT^Z99") == options


def test_legacy_ajax_options_keep_their_response_envelope(client, session):
    uf, uh, room, bed = _structure(session)

    uh_response = client.get(f"/mouvements/api/unites_hebergement/{uf.identifier}")
    room_response = client.get(f"/mouvements/api/chambres/{uh.id}")
    bed_response = client.get(f"/mouvements/api/lits/{room.id}")

    assert uh_response.json() == {
        "success": True,
        "options": [{"value": str(uh.id), "label": "UH options"}],
    }
    assert room_response.json()["options"][0]["value"] == str(room.id)
    assert bed_response.json()["options"][0]["value"] == str(bed.id)
