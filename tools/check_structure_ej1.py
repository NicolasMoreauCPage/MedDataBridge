from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import EntiteGeographique
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit

with Session(engine) as s:
    egs = s.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == 1)).all()
    for eg in egs:
        print('EG:', eg.id, eg.name)
        poles = s.exec(select(Pole).where(Pole.entite_geo_id == eg.id)).all()
        print('Poles:', [p.id for p in poles])
        services = s.exec(select(Service).where(Service.pole_id.in_([p.id for p in poles]))).all()
        print('Services:', [srv.id for srv in services])
        ufs = s.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id.in_([srv.id for srv in services]))).all()
        print('UFs:', [uf.id for uf in ufs])
        uhs = s.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id.in_([uf.id for uf in ufs]))).all()
        print('UHs:', [uh.id for uh in uhs])
        chambres = s.exec(select(Chambre).where(Chambre.unite_hebergement_id.in_([uh.id for uh in uhs]))).all()
        print('Chambres:', [ch.id for ch in chambres])
        lits = s.exec(select(Lit).where(Lit.chambre_id.in_([ch.id for ch in chambres]))).all()
        print('Lits:', [l.id for l in lits])
