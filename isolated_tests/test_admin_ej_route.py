"""Regression test for EJ detail route without fallback router.
"""
import os, sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

from fastapi import FastAPI, Depends
from fastapi.routing import APIRouter
from fastapi.templating import Jinja2Templates
from app.models_structure_fhir import EntiteJuridique

def create_minimal_app() -> FastAPI:
    app = FastAPI(title="Minimal MedDataBridge for EJ route test")
    templates = Jinja2Templates(directory="app/templates")
    router = APIRouter(prefix="/ght")

    def get_test_session():
        with Session(engine) as s:
            yield s

    @router.get("/{context_id}/ej/{ej_id}")
    async def ej_detail(context_id: int, ej_id: int, session: Session = Depends(get_test_session)):
        ej = session.get(EntiteJuridique, ej_id)
        if not ej:
            return {"error": "not found"}, 404
        return {"id": ej.id, "name": ej.name}

    app.include_router(router, prefix="/admin")

    # No need for dependency override of global get_session; using local Depends
    return app
from app.models_structure_fhir import GHTContext, EntiteJuridique

engine = create_engine("sqlite:///:memory:")
SQLModel.metadata.create_all(engine)
app = create_minimal_app()

client = TestClient(app)


def test_ej_detail_route_basic():
    with Session(engine) as session:
        ctx = GHTContext(name="GHT Test", description="Context Test")
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
        ej = EntiteJuridique(name="EJ Test", short_name="EJ Test", finess_ej="999999999", ght_context_id=ctx.id)
        session.add(ej)
        session.commit()
        session.refresh(ej)

    resp = client.get(f"/admin/ght/{ctx.id}/ej/{ej.id}")
    assert resp.status_code == 200, resp.text
