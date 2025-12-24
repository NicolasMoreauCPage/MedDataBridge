# tests/unit/test_fhir_import.py
"""
Tests unitaires pour l'import FHIR.
"""

import pytest
from sqlmodel import select
from datetime import datetime

from app.models import Patient, Dossier
from app.models_structure import EntiteJuridique, GHTContext


class TestFHIRImport:
    """Tests pour l'import FHIR"""

    def test_import_bundle_success(self, client, session):
        """Test import bundle FHIR - succès"""
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

        # Bundle FHIR minimal pour test
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "test-patient-1",
                        "name": [
                            {
                                "family": "Test",
                                "given": ["Patient"]
                            }
                        ]
                    },
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    }
                }
            ]
        }

        # Requête d'import
        import_request = {
            "bundle": bundle,
            "ej_id": ej.id
        }

        # Exécution
        response = client.post("/api/fhir/import/bundle", json=import_request)

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "resources_created" in data
        assert "resources_updated" in data
        assert "errors" in data

    def test_import_bundle_invalid_ej(self, client, session):
        """Test import bundle FHIR - EJ invalide"""
        # Bundle FHIR minimal
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": []
        }

        # Requête avec EJ inexistante
        import_request = {
            "bundle": bundle,
            "ej_id": 99999
        }

        # Exécution
        response = client.post("/api/fhir/import/bundle", json=import_request)

        # Vérifications
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_import_bundle_invalid_format(self, client, session):
        """Test import bundle FHIR - format invalide"""
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

        # Bundle invalide (pas de resourceType)
        invalid_bundle = {
            "type": "transaction",
            "entries": []
        }

        # Requête d'import
        import_request = {
            "bundle": invalid_bundle,
            "ej_id": ej.id
        }

        # Exécution
        response = client.post("/api/fhir/import/bundle", json=import_request)

        # Vérifications - devrait échouer avec erreur de validation
        assert response.status_code in [400, 422]
        data = response.json()
        assert "detail" in data

    def test_validate_bundle_success(self, client, session):
        """Test validation bundle FHIR - succès"""
        # Bundle FHIR valide
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "test-patient-1",
                        "name": [
                            {
                                "family": "Test",
                                "given": ["Patient"]
                            }
                        ]
                    }
                }
            ]
        }

        # Exécution
        response = client.post("/api/fhir/validate/bundle", json=bundle)

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert data["valid"] is True

    def test_validate_bundle_invalid(self, client, session):
        """Test validation bundle FHIR - invalide"""
        # Bundle invalide
        invalid_bundle = {
            "type": "invalid",
            "entries": []
        }

        # Exécution
        response = client.post("/api/fhir/validate/bundle", json=invalid_bundle)

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert data["valid"] is False
        assert "errors" in data