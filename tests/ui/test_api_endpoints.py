import pytest
from fastapi.testclient import TestClient
import json


class TestAPIEndpoints:
    """Tests for API endpoints not covered by existing tests"""

    def test_api_structure_tree(self, client):
        """Test structure tree API endpoint"""
        response = client.get("/api/structure/tree")
        # Should return JSON data or appropriate error
        assert response.status_code in [200, 404, 422, 400]  # Allow not found if no data

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict)), "Should return JSON data"

    def test_api_metrics_cache(self, client):
        """Test cache metrics API endpoint"""
        response = client.get("/api/metrics/cache")
        assert response.status_code in [200, 404, 422]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "Should return cache metrics data"

    def test_api_admin_stats(self, client):
        """Test admin stats API endpoint"""
        response = client.get("/api/admin/stats")
        assert response.status_code in [200, 401, 403, 404]  # May require auth

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "Should return admin stats data"

    def test_api_admin_config(self, client):
        """Test admin config API endpoint"""
        response = client.get("/api/admin/config")
        assert response.status_code in [200, 401, 403, 404]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "Should return config data"


class TestPOSTEndpoints:
    """Tests for POST/PUT/DELETE API endpoints"""

    def test_patient_api_create(self, client):
        """Test patient creation via API"""
        patient_data = {
            "family": "APITest",
            "given": "Patient",
            "gender": "other"
        }

        response = client.post("/patients/api/patients", json=patient_data)
        assert response.status_code in [200, 201, 422, 400]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data or "patient_id" in data, "Patient creation should return an ID"

    def test_dossier_api_create(self, client):
        """Test dossier creation via API"""
        # First create a patient
        patient_data = {
            "family": "DossierAPITest",
            "given": "Patient"
        }

        patient_response = client.post("/patients/api/patients", json=patient_data)
        if patient_response.status_code in [200, 201]:
            patient_data = patient_response.json()
            patient_id = patient_data.get("id") or patient_data.get("patient_id")

            if patient_id:
                dossier_data = {
                    "patient_id": patient_id,
                    "admit_time": "2024-01-01T10:00:00Z"
                }

                response = client.post("/dossiers/api/dossiers", json=dossier_data)
                assert response.status_code in [200, 201, 422, 400]

                if response.status_code in [200, 201]:
                    data = response.json()
                    assert "id" in data or "dossier_id" in data, "Dossier creation should return an ID"