"""Tests UI pour Patients et Dossiers: list, new, create, detail, edit, delete (si supporté).
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import Patient, Dossier
from app.db import get_next_sequence, init_db

import pytest

@pytest.fixture(autouse=True, scope="module")
def setup_db():
    from app.db import engine
    from sqlmodel import SQLModel
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def test_patient_new_form_loads_full(client: TestClient):
    r = client.get("/patients/new")
    assert r.status_code == 200
    # Champs clés
    for field in ["family", "given", "gender", "birth_date"]:
        assert f'name="{field}"' in r.text


def test_create_patient_and_view(client: TestClient, session: Session):
    # Un contexte GHT est requis par le routeur patients, simuler sélection via admin GHT si présent
    from app.models_structure import GHTContext
    ctx = session.exec(select(GHTContext).where(GHTContext.code=="GHT-DEMO-INTEROP")).first()
    if not ctx:
        ctx = GHTContext(name="GHT Démo Interop", code="GHT-DEMO-INTEROP", is_active=True)
        session.add(ctx); session.commit(); session.refresh(ctx)

    resp = client.get(f"/admin/ght/{ctx.id}", follow_redirects=True)
    print("DEBUG: TestClient cookies after GHT context set:", client.cookies)

    payload = {
        "family": "TESTUI",
        "given": "John",
        "gender": "male",
        "birth_date": "1980-01-01",
    }
    r = client.post("/patients/new", data=payload, follow_redirects=True)
    assert r.status_code == 200

    # Vérifier via la page de liste (évite collision de sessions)
    r2 = client.get("/patients")
    assert r2.status_code == 200
    print("DEBUG: /patients HTML output:\n", r2.text)
    assert "TESTUI" in r2.text


def test_dossiers_list_and_new(client: TestClient, session: Session):
    # besoin d'un patient
    seq = get_next_sequence(session, "patient")
    patient = Patient(patient_seq=seq, identifier=str(seq), family="DOS", given="UI", gender="other")
    session.add(patient); session.commit(); session.refresh(patient)

    r = client.get("/dossiers")
    assert r.status_code == 200

    r2 = client.get("/dossiers/new")
    assert r2.status_code == 200
    assert 'name="patient_id"' in r2.text


def test_create_dossier_and_detail(client: TestClient, session: Session):
    # Sélection contexte GHT requis
    from app.models_structure import GHTContext
    ctx = session.exec(select(GHTContext).where(GHTContext.code=="GHT-DEMO-INTEROP")).first()
    if not ctx:
        ctx = GHTContext(name="GHT Démo Interop", code="GHT-DEMO-INTEROP", is_active=True)
        session.add(ctx); session.commit(); session.refresh(ctx)
    client.get(f"/admin/ght/{ctx.id}", follow_redirects=True)

    seq = get_next_sequence(session, "patient")
    patient = Patient(patient_seq=seq, identifier=str(seq), family="DOS2", given="UI", gender="F")
    session.add(patient); session.commit(); session.refresh(patient)

    # Définir le contexte patient
    client.get(f"/context/patient/{patient.id}", follow_redirects=True)

    from datetime import datetime
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M")
    payload = {
        "patient_id": str(patient.id),
        "admit_time": now_iso,
        "admission_source": "RD",  # Domicile
    }
    r = client.post("/dossiers/new", data=payload, follow_redirects=False)
    assert r.status_code in (303,302)

    session.expire_all()
    d = session.exec(select(Dossier).where(Dossier.patient_id==patient.id)).first()
    assert d is not None
    r2 = client.get(f"/dossiers/{d.id}")
    assert r2.status_code == 200
    assert "DOS2" in r2.text
