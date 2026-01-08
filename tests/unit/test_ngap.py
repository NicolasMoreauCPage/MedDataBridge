# tests/test_ngap.py
"""
Tests pour les actes NGAP
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import NGAPAct, Dossier, Patient, SQLModel
from app.services.ngap_service import NGAPService
from app.api.ngap import NGAPActCreate


@pytest.fixture
def db_session():
    """Fixture pour la session de base de données de test"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_dossier(db_session):
    """Fixture pour créer un dossier de test"""
    patient = Patient(
        identifier="TEST123",
        family="Doe",
        given="John",
        birth_date=datetime(1980, 1, 1).date()
    )
    db_session.add(patient)
    db_session.commit()

    dossier = Dossier(
        dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
        patient_id=patient.id,
        admit_time=datetime.now()
    )
    db_session.add(dossier)
    db_session.commit()
    return dossier


def test_create_ngap_act(db_session, sample_dossier):
    """Test de création d'un acte NGAP"""
    service = NGAPService(db_session)

    act_data = NGAPActCreate(
        dossier_id=sample_dossier.id,
        lettre_cle="A",
        coefficient=1.5,
        execute_date=datetime.now(),
        montant=25.50,
        commentaire="Test acte"
    )

    act = service.create_act(act_data)

    assert act.dossier_id == sample_dossier.id
    assert act.lettre_cle == "A"
    assert act.coefficient == 1.5
    assert act.montant == 25.50
    assert act.commentaire == "Test acte"
    assert not act.valide
    assert not act.facture


def test_get_acts_by_dossier(db_session, sample_dossier):
    """Test de récupération des actes par dossier"""
    service = NGAPService(db_session)

    # Créer deux actes
    act1_data = NGAPActCreate(
        dossier_id=sample_dossier.id,
        lettre_cle="A",
        coefficient=1.0,
        execute_date=datetime.now()
    )
    act2_data = NGAPActCreate(
        dossier_id=sample_dossier.id,
        lettre_cle="B",
        coefficient=2.0,
        execute_date=datetime.now()
    )

    service.create_act(act1_data)
    service.create_act(act2_data)

    acts = service.get_acts_by_dossier(sample_dossier.id)

    assert len(acts) == 2
    assert acts[0].lettre_cle == "A"
    assert acts[1].lettre_cle == "B"


def test_validate_act(db_session, sample_dossier):
    """Test de validation d'un acte"""
    service = NGAPService(db_session)

    act_data = NGAPActCreate(
        dossier_id=sample_dossier.id,
        lettre_cle="C",
        coefficient=1.0,
        execute_date=datetime.now()
    )

    act = service.create_act(act_data)
    assert not act.valide

    validated_act = service.validate_act(act.id)
    assert validated_act.valide


def test_invalid_lettre_cle(db_session, sample_dossier):
    """Test avec lettre-clé invalide"""
    service = NGAPService(db_session)

    act_data = NGAPActCreate(
        dossier_id=sample_dossier.id,
        lettre_cle="1",  # Invalide
        coefficient=1.0,
        execute_date=datetime.now()
    )

    with pytest.raises(Exception):
        service.create_act(act_data)


def test_negative_coefficient(db_session, sample_dossier):
    """Test avec coefficient négatif"""
    service = NGAPService(db_session)

    act_data = NGAPActCreate(
        dossier_id=sample_dossier.id,
        lettre_cle="A",
        coefficient=-1.0,  # Invalide
        execute_date=datetime.now()
    )

    with pytest.raises(Exception):
        service.create_act(act_data)