"""
Exemple d'utilisation des nouvelles fixtures de conftest.py

Ce fichier montre comment les fixtures améliorées simplifient l'écriture des tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


def test_example_with_new_fixtures(sample_patient, sample_ght, sample_ej, sample_dossier):
    """Exemple montrant l'utilisation des nouvelles fixtures"""
    # Les fixtures créent automatiquement toutes les données nécessaires
    assert sample_patient.family == "Dupont"
    assert sample_patient.given == "Jean"
    assert sample_ght.name == "Test GHT"
    assert sample_ej.name == "Test EJ"
    assert sample_dossier.patient_id == sample_patient.id
    assert sample_dossier.entite_juridique_id == sample_ej.id


def test_context_router_with_fixtures(client: TestClient, sample_patient, sample_dossier):
    """Test utilisant les fixtures pour simplifier la création de données"""
    # Test de définition de contexte patient
    client.follow_redirects = False
    response = client.get(f"/context/patient/{sample_patient.id}")
    assert response.status_code == 303

    # Test de définition de contexte dossier
    response = client.get(f"/context/dossier/{sample_dossier.id}")
    assert response.status_code == 303


@pytest.fixture
def sample_patient_with_ght(session: Session, sample_ght):
    """Crée et retourne un patient associé à un GHT"""
    from app.models import Patient
    patient = Patient(
        family="Dupont",
        given="Jean",
        birth_date="1990-01-15",
        ght_context_id=sample_ght.id
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def test_patients_with_context(client: TestClient, sample_patient_with_ght, sample_ght):
    """Test de liste patients avec contexte GHT défini"""
    # Définir le contexte GHT
    client.follow_redirects = False
    client.get(f"/context/ght/{sample_ght.id}")

    # Maintenant la liste des patients devrait fonctionner
    response = client.get("/patients")
    assert response.status_code == 200
    assert "Dupont" in response.text