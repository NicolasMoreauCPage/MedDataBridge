"""
Tests API pour les endpoints UCD et LPP
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.api.ucd import router as ucd_router
from app.api.lpp import router as lpp_router
from app.schemas.ucd import UCDActCreate, UCDActUpdate, UCDActResponse
from app.schemas.lpp import LPPActCreate, LPPActUpdate, LPPActResponse


class TestUCDAPI:
    """Tests pour l'API UCD"""

    def setup_method(self):
        """Configuration avant chaque test"""
        self.client = TestClient(ucd_router)

    @patch('app.api.ucd.UCDService')
    def test_get_acts_by_dossier(self, mock_service):
        """Test récupération des actes UCD par dossier"""
        # Mock du service
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        # Mock des données de retour
        mock_acts = [
            UCDActResponse(
                id=1,
                code="1234567890123",
                libelle="Acte UCD 1",
                quantite=1,
                dossier_id=1
            ),
            UCDActResponse(
                id=2,
                code="9876543210987",
                libelle="Acte UCD 2",
                quantite=2,
                dossier_id=1
            )
        ]
        mock_service_instance.get_acts_by_dossier.return_value = mock_acts

        # Test de l'endpoint
        response = self.client.get("/api/ucd/dossier/1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["libelle"] == "Acte UCD 1"
        assert data[1]["libelle"] == "Acte UCD 2"

    @patch('app.api.ucd.UCDService')
    def test_get_act_by_id(self, mock_service):
        """Test récupération d'un acte UCD par ID"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_act = UCDActResponse(
            id=1,
            code="1234567890123",
            libelle="Acte UCD Test",
            quantite=1,
            dossier_id=1
        )
        mock_service_instance.get_act_by_id.return_value = mock_act

        response = self.client.get("/api/ucd/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["libelle"] == "Acte UCD Test"

    @patch('app.api.ucd.UCDService')
    def test_create_act(self, mock_service):
        """Test création d'un acte UCD"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_created_act = UCDActResponse(
            id=1,
            code="1234567890123",
            libelle="Nouvel acte UCD",
            quantite=1,
            dossier_id=1
        )
        mock_service_instance.create_act.return_value = mock_created_act

        act_data = {
            "code": "1234567890123",
            "libelle": "Nouvel acte UCD",
            "quantite": 1,
            "dossier_id": 1
        }

        response = self.client.post("/api/ucd/", json=act_data)

        assert response.status_code == 201
        data = response.json()
        assert data["libelle"] == "Nouvel acte UCD"

    @patch('app.api.ucd.UCDService')
    def test_update_act(self, mock_service):
        """Test mise à jour d'un acte UCD"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_updated_act = UCDActResponse(
            id=1,
            code="1234567890123",
            libelle="Acte modifié",
            quantite=1,
            dossier_id=1
        )
        mock_service_instance.update_act.return_value = mock_updated_act

        update_data = {
            "libelle": "Acte modifié"
        }

        response = self.client.put("/api/ucd/1", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["libelle"] == "Acte modifié"

    @patch('app.api.ucd.UCDService')
    def test_delete_act(self, mock_service):
        """Test suppression d'un acte UCD"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.delete_act.return_value = None

        response = self.client.delete("/api/ucd/1")

        assert response.status_code == 204
        mock_service_instance.delete_act.assert_called_once_with(1)


class TestLPPAPI:
    """Tests pour l'API LPP"""

    def setup_method(self):
        """Configuration avant chaque test"""
        self.client = TestClient(lpp_router)

    @patch('app.api.lpp.LPPService')
    def test_get_acts_by_dossier(self, mock_service):
        """Test récupération des actes LPP par dossier"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_acts = [
            LPPActResponse(
                id=1,
                code="1234567890123",
                libelle="Acte LPP 1",
                quantite=1,
                dossier_id=1
            ),
            LPPActResponse(
                id=2,
                code="9876543210987",
                libelle="Acte LPP 2",
                quantite=2,
                dossier_id=1
            )
        ]
        mock_service_instance.get_acts_by_dossier.return_value = mock_acts

        response = self.client.get("/api/lpp/dossier/1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["libelle"] == "Acte LPP 1"
        assert data[1]["libelle"] == "Acte LPP 2"

    @patch('app.api.lpp.LPPService')
    def test_get_act_by_id(self, mock_service):
        """Test récupération d'un acte LPP par ID"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_act = LPPActResponse(
            id=1,
            code="1234567890123",
            libelle="Acte LPP Test",
            quantite=1,
            dossier_id=1
        )
        mock_service_instance.get_act_by_id.return_value = mock_act

        response = self.client.get("/api/lpp/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["libelle"] == "Acte LPP Test"

    @patch('app.api.lpp.LPPService')
    def test_create_act(self, mock_service):
        """Test création d'un acte LPP"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_created_act = LPPActResponse(
            id=1,
            code="1234567890123",
            libelle="Nouvel acte LPP",
            quantite=1,
            dossier_id=1
        )
        mock_service_instance.create_act.return_value = mock_created_act

        act_data = {
            "code": "1234567890123",
            "libelle": "Nouvel acte LPP",
            "quantite": 1,
            "dossier_id": 1
        }

        response = self.client.post("/api/lpp/", json=act_data)

        assert response.status_code == 201
        data = response.json()
        assert data["libelle"] == "Nouvel acte LPP"

    @patch('app.api.lpp.LPPService')
    def test_update_act(self, mock_service):
        """Test mise à jour d'un acte LPP"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance

        mock_updated_act = LPPActResponse(
            id=1,
            code="1234567890123",
            libelle="Acte modifié",
            quantite=1,
            dossier_id=1
        )
        mock_service_instance.update_act.return_value = mock_updated_act

        update_data = {
            "libelle": "Acte modifié"
        }

        response = self.client.put("/api/lpp/1", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["libelle"] == "Acte modifié"

    @patch('app.api.lpp.LPPService')
    def test_delete_act(self, mock_service):
        """Test suppression d'un acte LPP"""
        mock_service_instance = AsyncMock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.delete_act.return_value = None

        response = self.client.delete("/api/lpp/1")

        assert response.status_code == 204
        mock_service_instance.delete_act.assert_called_once_with(1)