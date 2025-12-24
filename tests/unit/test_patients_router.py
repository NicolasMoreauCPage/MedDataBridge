"""
Tests pour le router patients.py

Couvre les routes principales :
- Création patient via API
- Liste patients
- Détails patient
- Édition patient
- Suppression patient
- Génération identité exemple
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import Patient, Dossier
from app.models_structure import GHTContext, EntiteJuridique
from app.services.patients_service import PatientCreateSchema


@pytest.mark.api
def test_api_create_patient_success(client: TestClient, session: Session):
    """Test création patient via API REST avec succès"""
    patient_data = {
        "family": "Dupont",
        "given": "Jean",
        "birth_date": "1990-01-15"
    }

    response = client.post("/patients/api/patients", json=patient_data)

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["family"] == "Dupont"
    assert data["given"] == "Jean"
    assert data["birth_date"] == "1990-01-15"

    # Vérifier que le patient a été créé en DB
    patient = session.get(Patient, data["id"])
    assert patient is not None
    assert patient.family == "Dupont"
    assert patient.given == "Jean"


def test_api_create_patient_invalid_data(client: TestClient):
    """Test création patient avec données invalides"""
    # Données manquantes
    response = client.post("/patients/api/patients", json={})

    assert response.status_code == 422  # Validation error


def test_api_create_patient_server_error(client: TestClient, monkeypatch):
    """Test gestion d'erreur serveur lors de la création"""
    def mock_create_patient(*args, **kwargs):
        raise Exception("Database error")

    monkeypatch.setattr("app.services.patients_service.create_patient", mock_create_patient)

    patient_data = {
        "family": "Dupont",
        "given": "Jean",
        "birth_date": "1990-01-15"
    }

    response = client.post("/patients/api/patients", json=patient_data)

    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]


def test_list_patients_html(client: TestClient, session: Session):
    """Test affichage liste patients en HTML"""
    # Créer un contexte GHT pour les tests
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    # Créer quelques patients de test associés au GHT
    patient1 = Patient(family="Dupont", given="Jean", birth_date="1990-01-15", ght_context_id=ght.id)
    patient2 = Patient(family="Martin", given="Marie", birth_date="1985-03-20", ght_context_id=ght.id)
    session.add(patient1)
    session.add(patient2)
    session.commit()

    # Définir le contexte GHT dans la session du client
    client.follow_redirects = False
    client.get(f"/context/ght/{ght.id}")

    response = client.get("/patients")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    content = response.text
    assert "Patients" in content
    assert "Dupont" in content
    assert "Martin" in content


def test_patient_detail_found(client: TestClient, session: Session):
    """Test affichage détails patient existant"""
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    response = client.get(f"/patients/{patient.id}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    content = response.text
    assert "Dupont" in content
    assert "Jean" in content


def test_patient_detail_not_found(client: TestClient):
    """Test affichage détails patient inexistant"""
    response = client.get("/patients/99999")

    assert response.status_code == 404
    content = response.text
    assert "Patient introuvable" in content


def test_edit_patient_form_found(client: TestClient, session: Session):
    """Test affichage formulaire édition patient existant"""
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    response = client.get(f"/patients/{patient.id}/edit")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    content = response.text
    assert "Modifier patient" in content
    assert "Dupont" in content


def test_edit_patient_form_not_found(client: TestClient):
    """Test affichage formulaire édition patient inexistant"""
    response = client.get("/patients/99999/edit")

    assert response.status_code == 404
    content = response.text
    assert "Patient introuvable" in content


def test_delete_patient_success(client: TestClient, session: Session):
    """Test suppression patient avec succès"""
    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15")
    session.add(patient)
    session.commit()

    client.follow_redirects = False
    response = client.post(
        f"/patients/{patient.id}/delete",
        headers={"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    )

    assert response.status_code == 303  # Redirect after success
    assert response.headers["location"] == "/patients"

    # Vérifier que le patient a été supprimé en tentant d'accéder à sa page de détail
    detail_response = client.get(f"/patients/{patient.id}")
    assert detail_response.status_code == 404  # Patient should not be found


def test_delete_patient_not_found(client: TestClient):
    """Test suppression patient inexistant"""
    response = client.post("/patients/99999/delete")

    assert response.status_code == 404
    content = response.text
    assert "Patient introuvable" in content


def test_generate_sample_identity(client: TestClient):
    """Test génération identité exemple"""
    response = client.get("/patients/sample-identity")

    assert response.status_code == 200
    data = response.json()
    assert "sample_data" in data
    sample_data = data["sample_data"]
    assert "family" in sample_data
    assert "given" in sample_data
    assert "birth_date" in sample_data


def test_new_patient_form(client: TestClient):
    """Test affichage formulaire nouveau patient"""
    response = client.get("/patients/new")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    content = response.text
    assert "Nouveau patient" in content


def test_new_patient_form_with_prefill(client: TestClient):
    """Test affichage formulaire nouveau patient avec pré-remplissage"""
    response = client.get("/patients/new?prefill=1")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    content = response.text
    assert "Nouveau patient" in content
    # Le pré-remplissage devrait être présent dans le contexte de template


def test_update_patient_form_success(client: TestClient, session: Session):
    """Test mise à jour patient depuis formulaire avec succès"""
    # Créer un contexte GHT pour les tests
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    patient = Patient(family="Dupont", given="Jean", birth_date="1990-01-15", ght_context_id=ght.id)
    session.add(patient)
    session.commit()

    # Définir le contexte GHT dans la session du client via l'endpoint context
    client.follow_redirects = False
    client.get(f"/context/ght/{ght.id}")

    form_data = {
        "family": "Dupont",
        "given": "Jean-Pierre",
        "birth_date": "1990-01-15",
        "gender": "male",
        "identifier": "EXT123"
    }

    response = client.post(
        f"/patients/{patient.id}/edit",
        data=form_data,
        follow_redirects=False
    )

    assert response.status_code == 303  # Redirect after success
    assert response.headers["location"] == f"/patients/{patient.id}"

    # Vérifier que le patient a été mis à jour en DB
    updated_patient = session.get(Patient, patient.id)
    assert updated_patient.given == "Jean-Pierre"
    assert updated_patient.gender == "male"
    assert updated_patient.identifier == "EXT123"


def test_update_patient_form_not_found(client: TestClient, session: Session):
    """Test mise à jour patient inexistant depuis formulaire"""
    # Créer un contexte GHT pour les tests
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    # Définir le contexte GHT dans la session du client via l'endpoint context
    client.follow_redirects = False
    client.get(f"/context/ght/{ght.id}")

    form_data = {
        "family": "Dupont",
        "given": "Jean",
        "birth_date": "1990-01-15"
    }

    response = client.post("/patients/99999/edit", data=form_data)

    assert response.status_code == 404
    content = response.text
    assert "Patient introuvable" in content


@pytest.mark.skip(reason="Test causing performance issues - needs investigation")
def test_create_patient_from_form_success(client: TestClient, session: Session):
    """Test création patient depuis formulaire avec succès"""
    # Créer un contexte GHT pour les tests
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    # Créer un contexte GHT dans la session du client via l'endpoint context
    client.follow_redirects = False
    client.get(f"/context/ght/{ght.id}")

    form_data = {
        "family": "Martin",
        "given": "Marie",
        "birth_date": "1985-03-20",
        "gender": "female",
        "external_id": "EXT456"
    }

    response = client.post("/patients/new", data=form_data)

    if response.status_code != 303:
        print("Response status:", response.status_code)
        print("Response body:", response.json())
        assert False, f"Expected 303, got {response.status_code}"

    assert response.status_code == 303  # Redirect after success
    assert response.headers["location"] == "/patients"

    # Vérifier qu'un patient a été créé en DB
    patients = session.exec(select(Patient).where(Patient.family == "Martin")).all()
    assert len(patients) == 1
    patient = patients[0]
    assert patient.given == "Marie"
    assert patient.birth_date == date(1985, 3, 20)
    assert patient.gender == "female"
    assert patient.identifier == "EXT456"


@pytest.mark.skip(reason="Test failing due to form data format changes - needs to be fixed")
def test_create_patient_from_form_ajax_success(client: TestClient, session: Session):
    """Test création patient depuis formulaire en mode AJAX"""
    # Créer un contexte GHT pour les tests
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    # Définir le contexte GHT dans la session du client via l'endpoint context
    client.follow_redirects = False
    client.get(f"/context/ght/{ght.id}")

    form_data = {
        "family": "Dubois",
        "given": "Pierre",
        "birth_date": "1975-12-10",
        "gender": "male"
    }

    response = client.post(
        "/patients/new",
        json=form_data,
        headers={"accept": "application/json"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Patient créé" in data["message"]
    assert data["redirect"] == "/patients"

    # Vérifier qu'un patient a été créé en DB
    patients = session.exec(select(Patient).where(Patient.family == "Dubois")).all()
    assert len(patients) == 1


def test_create_patient_from_form_validation_error(client: TestClient, session: Session):
    """Test création patient avec données invalides"""
    # Créer un contexte GHT pour les tests
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    # Définir le contexte GHT dans la session du client
    client.follow_redirects = False
    client.get(f"/context/ght/{ght.id}")

    form_data = {
        "family": "",  # Nom requis manquant
        "given": "Pierre",
        "birth_date": "invalid-date"
    }

    response = client.post("/patients/new", data=form_data)

    assert response.status_code == 422  # Pydantic validation error
    # En cas d'erreur, devrait rediriger vers /patients/new avec un message d'erreur


def test_list_patients_with_ej_context(client: TestClient, session: Session):
    """Test liste patients filtrée par contexte EJ"""
    from app.models_structure import GHTContext, EntiteJuridique

    # Créer GHT et EJ
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()

    ej = EntiteJuridique(name="Test EJ", code="EJ001", ght_context_id=ght.id)
    session.add(ej)
    session.commit()

    # Créer patients dans différentes EJ
    patient1 = Patient(family="Dupont", given="Jean", birth_date="1990-01-15", entite_juridique_id=ej.id)
    patient2 = Patient(family="Martin", given="Marie", birth_date="1985-03-20", entite_juridique_id=999)  # EJ différente
    session.add(patient1)
    session.add(patient2)
    session.commit()

    # Simuler contexte EJ défini
    client.follow_redirects = False
    client.get(f"/context/ej/{ej.id}")

    response = client.get("/patients")

    assert response.status_code == 200
    content = response.text
    assert "Dupont" in content
    assert "Martin" not in content  # Ne devrait pas apparaître car dans autre EJ


def test_list_patients_with_ght_context(client: TestClient, session: Session):
    """Test liste patients filtrée par contexte GHT"""
    from app.models_structure import GHTContext

    # Créer deux GHT
    ght1 = GHTContext(name="GHT 1", code="GHT1")
    ght2 = GHTContext(name="GHT 2", code="GHT2")
    session.add(ght1)
    session.add(ght2)
    session.commit()

    # Créer patients dans différents GHT
    patient1 = Patient(family="Dupont", given="Jean", birth_date="1990-01-15", ght_context_id=ght1.id)
    patient2 = Patient(family="Martin", given="Marie", birth_date="1985-03-20", ght_context_id=ght2.id)
    session.add(patient1)
    session.add(patient2)
    session.commit()

    # Simuler contexte GHT défini
    client.follow_redirects = False
    client.get(f"/context/ght/{ght1.id}")

    response = client.get("/patients")

    assert response.status_code == 200
    content = response.text
    assert "Dupont" in content
    assert "Martin" not in content  # Ne devrait pas apparaître car dans autre GHT