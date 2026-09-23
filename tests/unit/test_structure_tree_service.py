from app.models_structure import (
    Chambre,
    EntiteGeographique,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.structure_tree import build_structure_tree


def test_structure_tree_service_loads_and_projects_a_filtered_hierarchy(session):
    selected_eg = EntiteGeographique(identifier="EG-TREE-1", name="Site sélectionné")
    other_eg = EntiteGeographique(identifier="EG-TREE-2", name="Autre site")
    session.add_all([selected_eg, other_eg])
    session.flush()

    pole = Pole(identifier="POLE-TREE-1", name="Pôle", entite_geo_id=selected_eg.id)
    session.add(pole)
    session.flush()
    service = Service(identifier="SVC-TREE-1", name="Service", pole_id=pole.id)
    session.add(service)
    session.flush()
    uf = UniteFonctionnelle(identifier="UF-TREE-1", name="UF", service_id=service.id)
    session.add(uf)
    session.flush()
    uh = UniteHebergement(
        identifier="UH-TREE-1",
        name="UH",
        unite_fonctionnelle_id=uf.id,
    )
    session.add(uh)
    session.flush()
    chambre = Chambre(identifier="CH-TREE-1", name="Chambre", unite_hebergement_id=uh.id)
    session.add(chambre)
    session.flush()
    lit = Lit(identifier="LIT-TREE-1", name="Lit", chambre_id=chambre.id)
    session.add(lit)
    session.commit()

    tree = build_structure_tree(session, eg_ids=[selected_eg.id])

    assert len(tree) == 1
    eg_node = tree[0]
    assert eg_node["name"] == "Site sélectionné"
    pole_node = eg_node["poles"][0]
    service_node = pole_node["services"][0]
    uf_node = service_node["ufs"][0]
    uh_node = uf_node["unites_hebergement"][0]
    chambre_node = uh_node["chambres"][0]
    assert chambre_node["lits"] == [
        {"id": lit.id, "name": "Lit", "type": "lit", "status": "active"}
    ]


def test_structure_tree_service_keeps_strict_filtering_when_nothing_matches(session):
    session.add(EntiteGeographique(identifier="EG-TREE-ONLY", name="Site"))
    session.commit()

    assert build_structure_tree(session, eg_ids=[999_999]) == []
