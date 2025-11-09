"""Isolated test for extended multi-EJ seed without requiring Redis or full app import.
(Placed outside the main tests/ directory to avoid loading heavy conftest.)
"""
import os, sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
os.environ["TESTING"] = "1"

from sqlmodel import SQLModel, create_engine, select, Session

from app.models_structure_fhir import GHTContext, EntiteJuridique
from app.models_transport import SystemEndpoint
from app.models import Patient, Venue, Mouvement
from app.services.structure_seed import (
    ensure_extended_demo_ght,
    ensure_endpoints_for_context,
    seed_demo_population,
)

engine = create_engine("sqlite:///:memory:")
SQLModel.metadata.create_all(engine)

def session_factory_local():
    def _factory():
        return Session(engine)
    return _factory

def build_session_factory(_engine):  # simple shim
    def factory():
        return Session(_engine)
    return factory

SessionLocal = build_session_factory(engine)


def test_multi_ej_extended_seed_isolated():
    with SessionLocal() as session:
        ctx = GHTContext(name="GHT Demo", description="GHT multi-EJ demo")
        session.add(ctx)
        session.commit()
        session.refresh(ctx)

        ensure_extended_demo_ght(session, ctx)
        ej_count = session.exec(select(EntiteJuridique)).all()
        assert len(ej_count) == 4

        finess_list = [ej.finess_ej for ej in ej_count]
        ensure_endpoints_for_context(session, ctx, finess_list)
        endpoints = session.exec(select(SystemEndpoint)).all()
        assert len(endpoints) >= 12

        stats1 = seed_demo_population(session, ctx, target_patients=120)
        assert stats1.get("patients_created", 0) > 0
        patients1 = session.exec(select(Patient)).all()
        assert len(patients1) == 120
        movements1 = session.exec(select(Mouvement)).all()
        assert len(movements1) > 0

        stats2 = seed_demo_population(session, ctx, target_patients=120)
        assert stats2.get("patients_created", 0) == 0
        patients2 = session.exec(select(Patient)).all()
        assert len(patients2) == 120

        ensure_endpoints_for_context(session, ctx, finess_list)
        endpoints_after = session.exec(select(SystemEndpoint)).all()
        assert len(endpoints_after) == len(endpoints)
