from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import GHTContext

with Session(engine) as s:
    ghts = s.exec(select(GHTContext)).all()
    for ght in ghts:
        print({'id': ght.id, 'name': ght.name})
