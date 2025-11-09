"""Isolated test for extended multi-EJ seed without requiring Redis or full app import.

This test directly uses SQLModel with an in-memory SQLite database and the core
seeding functions to validate that the multi-EJ dataset initializes correctly.
It avoids importing `app.app` (which triggers Redis/cache and MLLP managers) to
stay independent of external services.

We only assert structural essentials:
- 4 Entités Juridiques
- Endpoints created per EJ (>= 3 per EJ: MLLP IN, MLLP OUT, FHIR EXPORT) if endpoint seeding is invoked
- Patient population seeded up to target count (default 120) with movements

Edge cases handled:
- Re-running the seed is idempotent (no duplicate EJ records)
- Second population run does not create additional patients if target already met

Note: This test does not rely on any global pytest fixtures; it builds its own
engine and session. If the repository has a global `conftest.py` that sets TESTING
flags, we explicitly set TESTING=1 to bypass side-effects.
"""
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.pool import StaticPool
import os

# Ensure TESTING flag to bypass side-effects in imported modules
os.environ["TESTING"] = "1"

from app.models_structure_fhir import GHTContext, EntiteJuridique
from app.models_transport import SystemEndpoint
from app.models import Patient, Venue, Mouvement
from app.services.structure_seed import (
    ensure_extended_demo_ght,
    ensure_endpoints_for_context,
    seed_demo_population,
)
# Build isolated in-memory engine (sqlite) with StaticPool so multiple sessions share state
engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def test_multi_ej_extended_seed_isolated():
    with Session(engine) as session:
        # Create a GHT context manually (normally created by init_db)
        ctx = GHTContext(name="GHT Demo", description="GHT multi-EJ demo")
        session.add(ctx)
        session.commit()
        session.refresh(ctx)

        # Structure seed (multi-EJ)
        ensure_extended_demo_ght(session, ctx)

        ej_count = session.exec(select(EntiteJuridique)).all()
        assert len(ej_count) == 4, f"Expected 4 EJ, got {len(ej_count)}"

        # Endpoints per EJ
        finess_list = [ej.finess_ej for ej in ej_count]
        ensure_endpoints_for_context(session, ctx, finess_list)
        endpoints = session.exec(select(SystemEndpoint)).all()
        assert len(endpoints) >= 12, f"Expected >=12 endpoints, got {len(endpoints)}"

        # Patient population first run
        pop_stats_1 = seed_demo_population(session, ctx, target_patients=120)
        assert pop_stats_1.get("skipped") is None, "First run should not skip creation"
        total_patients_1 = session.exec(select(Patient)).all()
        assert len(total_patients_1) == 120, f"Expected 120 patients after first run, got {len(total_patients_1)}"
        movements_1 = session.exec(select(Mouvement)).all()
        assert len(movements_1) > 0, "Mouvements should have been generated"

        # Second run idempotence
        pop_stats_2 = seed_demo_population(session, ctx, target_patients=120)
        assert pop_stats_2.get("skipped") == 120, "Second run should skip (already at target)"
        total_patients_2 = session.exec(select(Patient)).all()
        assert len(total_patients_2) == 120, "Patient count should remain stable after second run"

        # Endpoints stable on re-run
        ensure_endpoints_for_context(session, ctx, finess_list)
        endpoints_after = session.exec(select(SystemEndpoint)).all()
        assert len(endpoints_after) == len(endpoints), "Endpoint count should be stable (upsert, no duplicates)"


def test_re_run_structure_idempotent():
    with Session(engine) as session:
        ctx = GHTContext(name="GHT Demo 2", description="Second context")
        session.add(ctx)
        session.commit()
        session.refresh(ctx)

        ensure_extended_demo_ght(session, ctx)
        ensure_extended_demo_ght(session, ctx)

        ej_records = session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ctx.id)).all()
        assert len(ej_records) == 4, "Re-running structure seed must not create duplicate EJ"
