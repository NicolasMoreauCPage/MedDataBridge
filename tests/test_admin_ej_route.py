"""Regression test to ensure EJ detail route works without fallback router.

This uses TestClient with TESTING=1 to avoid side-effects (DB init, MLLP servers).
A temporary in-memory DB is set up; structure seed creates EJ entries so the
/admin/ght/{context_id}/ej/{ej_id} route should return 200.
"""
import os
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

from app.app import create_app  # use factory to avoid production side-effects
from app.models_structure_fhir import GHTContext
from app.services.structure_seed import ensure_extended_demo_ght, ensure_endpoints_for_context


def build_inmemory_app():
    """Create an in‑memory app + engine suitable for multi‑session access.

    Uses StaticPool + check_same_thread False so that each new session created
    by FastAPI dependencies sees the same in‑memory database (schema + data).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    app = create_app()

    # Patch dependency to use our in-memory engine for session
    from app.db import get_session as original_get_session

    def get_test_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[original_get_session] = get_test_session
    return app, engine


def test_ej_detail_route_works():
    app, engine = build_inmemory_app()
    # Prepare data inside a single open session so commits are flushed before TestClient usage
    with Session(engine) as session:
        ctx = GHTContext(name="GHT Test", description="Context Test")
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
        ensure_extended_demo_ght(session, ctx)
        # Seed endpoints so template has related context if needed
        from sqlmodel import select
        from app.models_structure_fhir import EntiteJuridique
        ej_list = session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ctx.id)).all()
        finess_list = [ej.finess_ej for ej in ej_list]
        ensure_endpoints_for_context(session, ctx, finess_list)
        ctx_id = ctx.id

    client = TestClient(app)

    # EJ IDs start at 1 after seed
    resp = client.get(f"/admin/ght/{ctx_id}/ej/1")
    assert resp.status_code == 200, resp.text
    # Basic sanity: page should contain EJ finess or name
    assert "CHU" in resp.text or "EJ" in resp.text or "Entité" in resp.text
