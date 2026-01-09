"""
Test d'intégration pour les cotations HPRIM
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from app.app import app
from app.db_session_factory import get_session
from app.models import Patient, Dossier, DossierType, CCAMAct
from datetime import datetime


@pytest.fixture(name="session")
def session_fixture():
    """Créer une session de test en mémoire"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Créer un client FastAPI avec la session de test"""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_cotations_count_no_cotations(client: TestClient, session: Session):
    """Test: compter les cotations d'un dossier sans cotations"""
    
    # Créer un patient et dossier de test
    patient = Patient(
        family="Dupont",
        given="Jean",
        dob=datetime(1980, 1, 1),
    )
    session.add(patient)
    session.flush()
    
    dossier = Dossier(
        dossier_seq=1001,
        patient_id=patient.id,
        admit_time=datetime.now(),
        dossier_type=DossierType.HOSPITALISE,
    )
    session.add(dossier)
    session.commit()
    
    # Tester l'endpoint
    response = client.get(f"/api/hprim/interventions/{dossier.id}/cotations-count")
    assert response.status_code == 200
    
    data = response.json()
    assert data["dossier_id"] == dossier.id
    assert data["cotations_count"] == 0
    assert data["has_cotations"] is False


def test_cotations_count_with_cotations(client: TestClient, session: Session):
    """Test: compter les cotations d'un dossier avec cotations"""
    
    # Créer un patient et dossier de test
    patient = Patient(
        family="Martin",
        given="Marie",
        dob=datetime(1985, 3, 15),
    )
    session.add(patient)
    session.flush()
    
    dossier = Dossier(
        dossier_seq=1002,
        patient_id=patient.id,
        admit_time=datetime.now(),
        dossier_type=DossierType.HOSPITALISE,
    )
    session.add(dossier)
    session.flush()
    
    # Ajouter un acte CCAM
    ccam_act = CCAMAct(
        code_acte="AAAA001",
        code_activite="01",
        execute_date=datetime.now(),
        dossier_id=dossier.id,
    )
    session.add(ccam_act)
    session.commit()
    
    # Tester l'endpoint
    response = client.get(f"/api/hprim/interventions/{dossier.id}/cotations-count")
    assert response.status_code == 200
    
    data = response.json()
    assert data["dossier_id"] == dossier.id
    assert data["cotations_count"] == 1
    assert data["has_cotations"] is True


def test_acquittement_processing(client: TestClient):
    """Test: traiter un message d'acquittement"""
    
    acquittement_data = {
        "statut": "OK",
        "message_id_original": "MSG-TEST-001",
        "reponses_actes": [
            {
                "identifiant_acte": "CCAM-001",
                "type_acte": "CCAM",
                "code": "AAAA001",
                "statut": "OK"
            },
            {
                "identifiant_acte": "CCAM-002",
                "type_acte": "CCAM",
                "code": "AAAA002",
                "statut": "ERREUR",
                "codeErreur": "ERR-001",
                "messageErreur": "Acte non reconnu"
            }
        ]
    }
    
    response = client.post("/api/hprim/acquittements/process", json=acquittement_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert data["message_id_original"] == "MSG-TEST-001"
    assert data["statut"] == "OK"
    assert data["reponses_count"]["actes"] == 2
    assert "date_acquittement" in data


def test_dossier_cotations_flags_update(client: TestClient, session: Session):
    """Test: mettre à jour les flags has_cotations et cotations_count"""
    
    # Créer un patient et dossier
    patient = Patient(
        family="Leclerc",
        given="Pierre",
        dob=datetime(1990, 6, 20),
    )
    session.add(patient)
    session.flush()
    
    dossier = Dossier(
        dossier_seq=1003,
        patient_id=patient.id,
        admit_time=datetime.now(),
        dossier_type=DossierType.HOSPITALISE,
    )
    session.add(dossier)
    session.flush()
    
    # Ajouter une cotation
    ccam_act = CCAMAct(
        code_acte="AAAA001",
        code_activite="01",
        execute_date=datetime.now(),
        dossier_id=dossier.id,
    )
    session.add(ccam_act)
    session.commit()
    
    # Mettre à jour les flags
    response = client.post(f"/api/hprim/interventions/{dossier.id}/update-cotations-flags")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    
    # Vérifier que le dossier est mis à jour
    session.refresh(dossier)
    assert dossier.has_cotations is True
    assert dossier.cotations_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
