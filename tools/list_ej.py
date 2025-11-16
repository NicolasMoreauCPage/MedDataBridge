from sqlmodel import Session, select
from app.db import engine
from app.models_structure import EntiteJuridique

with Session(engine) as session:
    print("ID | FINESS_EJ | NAME")
    for ej in session.exec(select(EntiteJuridique)).all():
        print(f"{ej.id} | {ej.finess_ej} | {ej.name}")from sqlmodel import Session, select
from app.db import engine
from app.models_structure import EntiteJuridique

with Session(engine) as s:
    ejs = s.exec(select(EntiteJuridique)).all()
    for ej in ejs:
        print({'id': ej.id, 'name': ej.name, 'finess_ej': ej.finess_ej, 'ght_context_id': ej.ght_context_id})
