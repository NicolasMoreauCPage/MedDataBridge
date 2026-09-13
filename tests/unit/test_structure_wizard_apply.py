from sqlmodel import select

from app.models_structure import Chambre, EntiteGeographique, Lit, UniteFonctionnelle, UniteHebergement


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
    uh = session.exec(select(UniteHebergement).where(UniteHebergement.name == "UH test")).one()
    chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()
    lits = session.exec(select(Lit).join(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()

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
