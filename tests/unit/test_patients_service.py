"""
Tests unitaires pour les services patients (sans TestClient)
"""

import pytest
from sqlmodel import Session, select
from app.models import Patient
from app.services.patients_service import PatientCreateSchema, PatientUpdateSchema, create_patient, update_patient


@pytest.mark.unit
class TestPatientsService:
    """Tests unitaires pour le service patients"""

    def test_create_patient_success(self, session: Session):
        """Test création patient réussie"""
        patient_data = PatientCreateSchema(
            family="Dupont",
            given="Jean",
            birth_date="1990-01-15"
        )

        patient = create_patient(session=session, patient_data=patient_data)

        assert patient.id is not None
        assert patient.family == "Dupont"
        assert patient.given == "Jean"
        assert str(patient.birth_date) == "1990-01-15"

    def test_update_patient_success(self, session: Session):
        """Test mise à jour patient réussie"""
        # Créer un patient
        patient_data = PatientCreateSchema(
            family="Dupont",
            given="Jean"
        )
        patient = create_patient(session=session, patient_data=patient_data)

        # Mettre à jour
        update_data = PatientUpdateSchema(
            family="Dupont",
            given="Jean-Pierre",
            gender="male",
            identifier="EXT123"
        )

        updated_patient = update_patient(session=session, patient=patient, patient_data=update_data)

        assert updated_patient.id == patient.id
        assert updated_patient.given == "Jean-Pierre"
        assert updated_patient.gender == "male"
        assert updated_patient.identifier == "EXT123"

    def test_update_patient_not_found(self, session: Session):
        """Test mise à jour patient inexistant"""
        update_data = PatientUpdateSchema(
            family="Test",
            given="User"
        )

        # Créer un patient factice pour le test
        fake_patient = Patient(family="Old", given="Name")

        with pytest.raises(Exception):  # Devrait lever une exception
            update_patient(session=session, patient=fake_patient, patient_data=update_data)