# tests/unit/test_fhir_export.py
"""
Tests unitaires pour l'export FHIR.
"""

import pytest
from sqlmodel import select
from datetime import datetime

from app.models import Patient, Dossier
from app.models_structure import EntiteJuridique, GHTContext


class TestFHIRExport:
    """Tests pour l'export FHIR"""

    def test_export_structure_success(self, client, session):
        """Test export structure FHIR - succès"""
        # Créer des données de test
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()

        # Créer une EJ
        ej = EntiteJuridique(
            name="Test EJ",
            code="TEST_EJ",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()

        # Exécution
        response = client.get(f"/api/fhir/export/structure/{ej.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "resourceType" in data
        assert data["resourceType"] == "Bundle"
        assert "entry" in data

    def test_export_structure_not_found(self, client, session):
        """Test export structure FHIR - EJ non trouvée"""
        # Exécution avec ID inexistant
        response = client.get("/api/fhir/export/structure/99999")

        # Vérifications
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entité juridique non trouvée" in data["detail"]

    def test_export_patient_success(self, client, session):
        """Test export patients FHIR - succès"""
        # Créer des données de test
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()

        # Créer une EJ
        ej = EntiteJuridique(
            name="Test EJ",
            code="TEST_EJ",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()

        # Créer un patient
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()

        # Exécution - export de tous les patients de l'EJ
        response = client.get(f"/api/fhir/export/patients/{ej.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "resourceType" in data
        assert data["resourceType"] == "Bundle"
        assert "entry" in data

    def test_export_patients_not_found(self, client, session):
        """Test export patients FHIR - EJ non trouvée"""
        # Exécution avec ID EJ inexistant
        response = client.get("/api/fhir/export/patients/99999")

        # Vérifications
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entité juridique non trouvée" in data["detail"]

    def test_export_dossier_success(self, client, session):
        """Test export complet FHIR - succès"""
        # Créer des données de test
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()

        # Créer une EJ
        ej = EntiteJuridique(
            name="Test EJ",
            code="TEST_EJ",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()

        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()

        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()

        # Exécution - export complet de l'EJ
        response = client.get(f"/api/fhir/export/all/{ej.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "structure" in data
        assert "patients" in data
        assert "venues" in data
        assert data["patients"]["resourceType"] == "Bundle"