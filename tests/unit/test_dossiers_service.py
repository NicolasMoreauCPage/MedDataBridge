"""
Tests unitaires pour les services dossiers (sans TestClient)
"""

import pytest
from datetime import datetime
from sqlmodel import Session, select
from app.models import Dossier, Patient, DossierType
from app.models_structure import EntiteJuridique
from app.services.dossiers_service import (
    DossierCreateSchema,
    DossierUpdateSchema,
    create_dossier,
    create_dossier_with_pre_admit_venue,
    update_dossier,
    get_dossier,
    get_dossiers
)


class TestDossiersService:
    """Tests unitaires pour le service dossiers"""

    def test_create_dossier_success(self, session: Session):
        """Test création dossier réussie"""
        # Créer des données de test
        patient = Patient(family="Test", given="User")
        session.add(patient)

        ej = EntiteJuridique(name="Test EJ", code="TEST_EJ")
        session.add(ej)
        session.commit()

        admit_time = datetime.now()
        dossier = create_dossier(
            session=session,
            patient_id=patient.id,
            ej_id=ej.id,
            dossier_type=DossierType.HOSPITALISE,
            admit_time=admit_time
        )

        assert dossier.id is not None
        assert dossier.patient_id == patient.id
        assert dossier.dossier_type == DossierType.HOSPITALISE
        assert dossier.dossier_seq is not None
        assert dossier.admit_time == admit_time

    def test_create_dossier_minimal(self, session: Session):
        """Test création dossier avec données minimales"""
        # Créer des données de test
        patient = Patient(family="Test", given="User")
        session.add(patient)

        ej = EntiteJuridique(name="Test EJ", code="TEST_EJ")
        session.add(ej)
        session.commit()

        dossier = create_dossier(
            session=session,
            patient_id=patient.id,
            ej_id=ej.id
        )

        assert dossier.id is not None
        assert dossier.patient_id == patient.id
        assert dossier.dossier_type == DossierType.HOSPITALISE  # valeur par défaut
        assert dossier.dossier_seq is not None

    def test_get_dossier_success(self, session: Session):
        """Test récupération dossier par ID"""
        # Créer un dossier
        patient = Patient(family="Test", given="User")
        session.add(patient)

        ej = EntiteJuridique(name="Test EJ", code="TEST_EJ")
        session.add(ej)
        session.commit()

        dossier = create_dossier(session, patient.id, ej.id)

        # Récupérer le dossier
        retrieved = get_dossier(session, dossier.id)

        assert retrieved is not None
        assert retrieved.id == dossier.id
        assert retrieved.patient_id == patient.id

    def test_get_dossier_not_found(self, session: Session):
        """Test récupération dossier inexistant"""
        retrieved = get_dossier(session, 99999)
        assert retrieved is None

    def test_get_dossiers_by_patient(self, session: Session):
        """Test récupération dossiers par patient"""
        # Créer un patient avec deux dossiers
        patient = Patient(family="Test", given="User")
        session.add(patient)

        ej = EntiteJuridique(name="Test EJ", code="TEST_EJ")
        session.add(ej)
        session.commit()

        dossier1 = create_dossier(session, patient.id, ej.id, DossierType.HOSPITALISE)
        dossier2 = create_dossier(session, patient.id, ej.id, DossierType.EXTERNE)

        # Récupérer les dossiers du patient
        dossiers = get_dossiers(session, patient_id=patient.id)

        assert len(dossiers) == 2
        assert all(d.patient_id == patient.id for d in dossiers)

    def test_update_dossier_success(self, session: Session):
        """Test mise à jour dossier réussie"""
        # Créer un dossier
        patient = Patient(family="Test", given="User")
        session.add(patient)

        ej = EntiteJuridique(name="Test EJ", code="TEST_EJ")
        session.add(ej)
        session.commit()

        dossier = create_dossier(session, patient.id, ej.id)

        # Mettre à jour
        new_admit_time = datetime.now()
        update_data = DossierUpdateSchema(
            patient_id=patient.id,
            uf_responsabilite="UF001",
            dossier_type=DossierType.EXTERNE,
            admission_source="urgence",
            attending_provider="Dr. Smith",
            admit_time=new_admit_time,
            dossier_seq=dossier.dossier_seq
        )

        updated_dossier = update_dossier(session, dossier, update_data)

        # Vérifier que la mise à jour a été faite dans la base de données
        session.refresh(dossier)
        
        assert updated_dossier.id == dossier.id
        assert updated_dossier.dossier_type == DossierType.EXTERNE
        assert dossier.dossier_type == DossierType.EXTERNE  # Vérifier aussi l'objet original
        assert updated_dossier.admission_source == "urgence"
        assert updated_dossier.attending_provider == "Dr. Smith"