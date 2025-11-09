from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique

with Session(engine) as s:
    ghts = s.exec(select(GHTContext)).all()
    print('GHTs:', [(g.id, g.name, g.code) for g in ghts])
    ejs = s.exec(select(EntiteJuridique)).all()
    print('EJs:', [(e.id, e.name, e.finess_ej, e.ght_context_id) for e in ejs])
    egs = s.exec(select(EntiteGeographique)).all()
    print('EGs:', [(eg.id, eg.name, eg.identifier, eg.entite_juridique_id) for eg in egs])
