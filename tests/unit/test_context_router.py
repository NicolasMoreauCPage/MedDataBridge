"""
Tests pour le router context.py
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import Patient, Dossier
from app.models_structure import GHTContext


def test_set_patient_context_success(client: TestClient, session: Session):
    """Test définition contexte patient - succès"""
    # Créer un patient de test
    patient = Patient(family="Test", given="User")
    session.add(patient)
    session.commit()

    response = client.get(f"/context/patient/{patient.id}", follow_redirects=False)

    assert response.status_code == 303  # Redirect
    # Vérifier que l'ID patient est dans la session (difficile à tester directement avec TestClient)
    # On peut vérifier que la redirection va vers la bonne URL
    assert f"/patients/{patient.id}" in response.headers.get("location", "")


def test_set_patient_context_not_found(client: TestClient):
    """Test définition contexte patient - patient inexistant"""
    response = client.get("/context/patient/99999", follow_redirects=False)

    assert response.status_code == 303  # Redirect
    assert response.headers["location"] == "/patients"


def test_set_dossier_context_success(client: TestClient, session: Session):
    """Test définition contexte dossier - succès"""
    # Créer un patient et un dossier de test
    patient = Patient(family="Test", given="User")
    session.add(patient)
    session.commit()

    dossier = Dossier(patient_id=patient.id, admit_time="2023-01-01T00:00:00")
    session.add(dossier)
    session.commit()

    response = client.get(f"/context/dossier/{dossier.id}", follow_redirects=False)

    assert response.status_code == 303  # Redirect
    assert f"/dossiers/{dossier.id}" in response.headers.get("location", "")


def test_set_dossier_context_not_found(client: TestClient):
    """Test définition contexte dossier - dossier inexistant"""
    response = client.get("/context/dossier/99999", follow_redirects=False)

    assert response.status_code == 303  # Redirect
    assert response.headers["location"] == "/dossiers"


def test_clear_context_patient(client: TestClient):
    """Test effacement contexte patient"""
    response = client.get("/context/clear?kind=patient", follow_redirects=False)

    assert response.status_code == 303  # Redirect


def test_clear_context_dossier(client: TestClient):
    """Test effacement contexte dossier"""
    response = client.get("/context/clear?kind=dossier", follow_redirects=False)

    assert response.status_code == 303  # Redirect


def test_clear_context_ght(client: TestClient):
    """Test effacement contexte GHT"""
    response = client.get("/context/clear?kind=ght", follow_redirects=False)

    assert response.status_code == 303  # Redirect