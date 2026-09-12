"""Roundtrip MFN^M05 de structure entre deux bases indépendantes."""

from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session, select

import app.db  # noqa: F401 -- enregistre les modèles SQLModel et leurs FK
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    GHTContext,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.mfn_structure import generate_mfn_message, process_mfn_message


def _create_structure(engine, source: bool) -> tuple[int, str]:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ght = GHTContext(name="GHT MFN", code="GHT-MFN-RT")
        session.add(ght)
        session.flush()
        ej = EntiteJuridique(name="EJ MFN", identifier="EJ-MFN", ght_context_id=ght.id)
        session.add(ej)
        session.flush()
        if not source:
            session.commit()
            return ej.id, ""

        eg = EntiteGeographique(name="Site MFN", identifier="EG-MFN", entite_juridique_id=ej.id)
        session.add(eg)
        session.flush()
        pole = Pole(name="Pôle MFN", identifier="POLE-MFN", entite_geo_id=eg.id)
        session.add(pole)
        session.flush()
        service = Service(name="Service MFN", identifier="SERV-MFN", pole_id=pole.id)
        session.add(service)
        session.flush()
        uf = UniteFonctionnelle(name="UF MFN", identifier="UF-MFN", service_id=service.id)
        session.add(uf)
        session.flush()
        uh = UniteHebergement(name="UH MFN", identifier="UH-MFN", unite_fonctionnelle_id=uf.id)
        session.add(uh)
        session.flush()
        chambre = Chambre(name="Chambre MFN", identifier="CH-MFN", unite_hebergement_id=uh.id)
        session.add(chambre)
        session.flush()
        session.add(Lit(name="Lit MFN", identifier="LIT-MFN", chambre_id=chambre.id))
        session.commit()
        return ej.id, eg.identifier


def test_mfn_structure_roundtrip_between_independent_databases():
    source_engine = create_engine("sqlite://")
    target_engine = create_engine("sqlite://")
    _, source_eg_identifier = _create_structure(source_engine, source=True)
    target_ej_id, _ = _create_structure(target_engine, source=False)

    with Session(source_engine) as session:
        message = generate_mfn_message(session, eg_identifier=source_eg_identifier)
    assert "LOC|^^^^^M^^^^EJ-MFN" in message
    assert "LOC|^^^^^ETBL_GRPQ^^^^EG-MFN" in message

    with Session(target_engine) as session:
        results = process_mfn_message(message, session)
        assert all(result["status"] in {"success", "updated"} for result in results)

        target_ej = session.get(EntiteJuridique, target_ej_id)
        eg = session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == "EG-MFN")).one()
        pole = session.exec(select(Pole).where(Pole.identifier == "POLE-MFN")).one()
        service = session.exec(select(Service).where(Service.identifier == "SERV-MFN")).one()
        uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == "UF-MFN")).one()
        uh = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == "UH-MFN")).one()
        chambre = session.exec(select(Chambre).where(Chambre.identifier == "CH-MFN")).one()
        lit = session.exec(select(Lit).where(Lit.identifier == "LIT-MFN")).one()

        assert eg.entite_juridique_id == target_ej.id
        assert pole.entite_geo_id == eg.id
        assert service.pole_id == pole.id
        assert uf.service_id == service.id
        assert uh.unite_fonctionnelle_id == uf.id
        assert chambre.unite_hebergement_id == uh.id
        assert lit.chambre_id == chambre.id

        # Réimporter le même MFN met à jour les lignes sans les dupliquer.
        process_mfn_message(message, session)
        assert len(session.exec(select(EntiteGeographique)).all()) == 1
        assert len(session.exec(select(Pole)).all()) == 1
        assert len(session.exec(select(Lit)).all()) == 1
