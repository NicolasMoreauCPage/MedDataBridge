from sqlmodel import Session
from app.db import engine
from app.models_structure_fhir import EntiteGeographique, EntiteJuridique

with Session(engine) as s:
    ej = s.get(EntiteJuridique, 1)
    eg = EntiteGeographique(
        identifier='EG-TEST-1',
        name='Site Test',
        entite_juridique_id=ej.id,
        finess='700004591',
        is_active=True
    )
    s.add(eg)
    s.commit()
    print('Entité géographique créée:', eg.id)
