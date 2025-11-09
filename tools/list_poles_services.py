from sqlmodel import Session, select
from app.db import engine
from app.models_structure import Pole, Service

with Session(engine) as s:
    poles = s.exec(select(Pole)).all()
    print('Poles:', [(p.id, p.name, p.identifier, p.entite_geo_id) for p in poles])
    services = s.exec(select(Service)).all()
    print('Services:', [(srv.id, srv.name, srv.identifier, srv.pole_id) for srv in services])
