from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models_structure import (
    Chambre,
    EntiteGeographique,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.structure_template_application import (
    StructureTemplateValidationError,
    apply_structure_template,
)


def test_structure_wizard_creates_the_real_hosting_hierarchy(client, session):
    eg = EntiteGeographique(name="EG Assistant")
    session.add(eg)
    session.commit()

    response = client.post("/api/structure/apply-template", json={
        "eg_id": eg.id,
        "payload": {
            "poles": [{
                "name": "Pôle test",
                "services": [{
                    "name": "Service test",
                    "ufs": [{"name": "UF test", "code_um": "UF-TEST"}],
                }],
            }],
        },
        "uhs": [{
            "name": "UH test",
            "uf_ref": "0:0:0",
            "chambres": 2,
            "lits": 3,
        }],
    })

    assert response.status_code == 200
    assert response.json()["created_entities"] == {
        "poles": 1,
        "services": 1,
        "ufs": 1,
        "uhs": 1,
        "chambres": 2,
        "lits": 3,
    }
    uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.name == "UF test")).one()
    service = session.exec(select(Service).where(Service.name == "Service test")).one()
    pole = session.exec(select(Pole).where(Pole.name == "Pôle test")).one()
    uh = session.exec(select(UniteHebergement).where(UniteHebergement.name == "UH test")).one()
    chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()
    lits = session.exec(select(Lit).join(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()

    assert pole.entite_geo_id == eg.id
    assert service.pole_id == pole.id
    assert uf.service_id == service.id
    assert uf.um_code == "UF-TEST"
    assert uh.unite_fonctionnelle_id == uf.id
    assert len(chambres) == 2
    assert len(lits) == 3


def test_structure_wizard_rejects_beds_without_a_room(client, session):
    eg = EntiteGeographique(name="EG Contrôle Assistant")
    session.add(eg)
    session.commit()

    response = client.post("/api/structure/apply-template", json={
        "eg_id": eg.id,
        "payload": {"poles": [{"name": "Pôle", "services": [{"name": "Service", "ufs": [{"name": "UF"}]}]}]},
        "uhs": [{"name": "UH invalide", "uf_ref": "0:0:0", "chambres": 0, "lits": 1}],
    })

    assert response.status_code == 422
    assert "lits sans chambre" in response.json()["detail"]
    assert session.exec(
        select(UniteHebergement).where(UniteHebergement.name == "UH invalide")
    ).first() is None


def test_structure_wizard_rejects_an_empty_or_unnamed_structure(client, session):
    eg = EntiteGeographique(name="EG Validation Assistant")
    session.add(eg)
    session.commit()

    for payload, expected_message in [
        ({"poles": []}, "au moins un pôle"),
        ({"poles": [{"name": "  "}]}, "doit avoir un nom"),
    ]:
        response = client.post("/api/structure/apply-template", json={
            "eg_id": eg.id,
            "payload": payload,
            "uhs": [],
        })

        assert response.status_code == 422
        assert expected_message in response.json()["detail"]


def test_structure_wizard_rejects_unnamed_nested_entities(client, session):
    eg = EntiteGeographique(name="EG Noms imbriqués")
    session.add(eg)
    session.commit()

    invalid_payloads = [
        ({"poles": [{"name": "Pôle", "services": [{"name": " "}]}]}, [], "Le service"),
        ({"poles": [{"name": "Pôle", "services": [{"name": "Service", "ufs": [{"name": ""}]}]}]}, [], "L'UF"),
        ({"poles": [{"name": "Pôle", "services": [{"name": "Service", "ufs": [{"name": "UF"}]}]}]}, [{"name": " ", "uf_ref": "0:0:0"}], "hébergement"),
    ]
    for payload, uhs, expected_message in invalid_payloads:
        response = client.post("/api/structure/apply-template", json={
            "eg_id": eg.id,
            "payload": payload,
            "uhs": uhs,
        })

        assert response.status_code == 422
        assert expected_message in response.json()["detail"]


def test_structure_template_service_validates_before_writing(session):
    eg = EntiteGeographique(name="EG transaction")
    session.add(eg)
    session.commit()

    with pytest.raises(StructureTemplateValidationError, match="lits sans chambre"):
        apply_structure_template(
            session,
            eg_id=eg.id,
            payload={
                "poles": [
                    {
                        "name": "Pôle transaction",
                        "services": [
                            {"name": "Service", "ufs": [{"name": "UF"}]}
                        ],
                    }
                ]
            },
            hosting_units=[
                SimpleNamespace(
                    name="UH invalide",
                    uf_ref="0:0:0",
                    chambres=0,
                    lits=1,
                )
            ],
        )

    assert session.exec(select(Pole).where(Pole.name == "Pôle transaction")).first() is None
