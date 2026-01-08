from app.db import engine
from sqlmodel import Session, select
from app.models_shared import SystemEndpoint

with Session(engine) as s:
    endpoints = s.exec(select(SystemEndpoint)).all()
    for e in endpoints:
        print(f'id={e.id}, name={e.name}, kind={e.kind}, role={e.role}, is_enabled={e.is_enabled}')
