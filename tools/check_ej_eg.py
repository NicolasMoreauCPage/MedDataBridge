from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import EntiteJuridique, EntiteGeographique

with Session(engine) as s:
    ej = s.get(EntiteJuridique, 1)
    print('EJ:', ej)
    egs = s.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej.id)).all()
    print('EGs:', [(eg.id, eg.name, eg.identifier) for eg in egs])
