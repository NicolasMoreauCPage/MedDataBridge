# tests/unit/test_services_ucd_lpp.py
"""
Tests unitaires pour les services UCD et LPP
"""

import pytest
from unittest.mock import Mock
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.ucd_service import UCDService
from app.services.lpp_service import LPPService
from app.schemas.ucd import UCDActCreate, UCDActUpdate, UCDActResponse
from app.schemas.lpp import LPPActCreate, LPPActUpdate, LPPActResponse
from app.models import UCDAct, LPPAct, Dossier


class TestUCDService:
    """Tests pour UCDService"""

    @pytest.fixture
    def mock_db(self):
        """Mock de la session de base de données"""
        return Mock(spec=Session)

    @pytest.fixture
    def ucd_service(self, mock_db):
        """Instance du service UCD avec mock DB"""
        return UCDService(mock_db)

    @pytest.fixture
    def sample_ucd_act(self):
        """Acte UCD de test"""
        return UCDAct(
            id=1,
            dossier_id=1,
            code_ucd="1234567890123",
            denomination_libelle="Acte UCD de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

    def test_init(self, ucd_service, mock_db):
        """Test d'initialisation du service"""
        assert ucd_service.db == mock_db

    def test_create_act(self, ucd_service, mock_db, sample_ucd_act):
        """Test de création d'acte UCD"""
        # Mock des données d'entrée
        act_data = UCDActCreate(
            dossier_id=1,
            code_ucd="1234567890123",  # Code CIP-13 valide (13 chiffres)
            denomination_libelle="Acte UCD de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

        # Mock de l'ajout en DB
        mock_db.get.return_value = Dossier(id=1)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 1))

        # Exécution
        result = ucd_service.create_act(act_data)

        # Vérifications
        assert isinstance(result, UCDActResponse)
        assert result.dossier_id == 1
        assert result.code_ucd == "1234567890123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_get_acts_by_dossier(self, ucd_service, mock_db, sample_ucd_act):
        """Test de récupération des actes UCD par dossier"""
        # Mock de la réponse
        expected_response = UCDActResponse(
            id=1,
            dossier_id=1,
            code_ucd="1234567890123",
            denomination_libelle="Acte UCD de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

        # Mock du service
        ucd_service.get_acts_by_dossier = Mock(return_value=[expected_response])

        # Exécution
        result = ucd_service.get_acts_by_dossier(1)

        # Vérifications
        assert len(result) == 1
        assert isinstance(result[0], UCDActResponse)
        assert result[0].id == 1

    def test_get_act_by_id(self, ucd_service, mock_db, sample_ucd_act):
        """Test de récupération d'un acte UCD par ID"""
        # Mock de la requête
        mock_db.get.return_value = sample_ucd_act

        # Exécution
        result = ucd_service.get_act_by_id(1)

        # Vérifications
        assert isinstance(result, UCDActResponse)
        assert result.id == 1
        mock_db.get.assert_called_once_with(UCDAct, 1)

    def test_update_act(self, ucd_service, mock_db, sample_ucd_act):
        """Test de mise à jour d'acte UCD"""
        # Mock de récupération
        mock_db.get.return_value = sample_ucd_act

        # Données de mise à jour
        update_data = UCDActUpdate(
            denomination_libelle="Acte modifié",
            montant_unitaire_facture_ttc=150.0,
            commentaire="Test modifié",
        )

        # Mock de commit
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Exécution
        result = ucd_service.update_act(1, update_data)

        # Vérifications
        assert isinstance(result, UCDActResponse)
        assert result.denomination_libelle == "Acte modifié"
        assert result.montant_unitaire_facture_ttc == 150.0
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_delete_act(self, ucd_service, mock_db, sample_ucd_act):
        """Test de suppression d'acte UCD"""
        # Mock de récupération
        mock_db.get.return_value = sample_ucd_act

        # Mock de suppression
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        # Exécution
        ucd_service.delete_act(1)

        # Vérifications
        mock_db.delete.assert_called_once_with(sample_ucd_act)
        mock_db.commit.assert_called_once()


class TestLPPService:
    """Tests pour LPPService"""

    @pytest.fixture
    def mock_db(self):
        """Mock de la session de base de données"""
        return Mock(spec=Session)

    @pytest.fixture
    def lpp_service(self, mock_db):
        """Instance du service LPP avec mock DB"""
        return LPPService(mock_db)

    @pytest.fixture
    def sample_lpp_act(self):
        """Acte LPP de test"""
        return LPPAct(
            id=1,
            dossier_id=1,
            code_lpp="1234567890123",
            denomination_libelle="Acte LPP de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

    def test_init(self, lpp_service, mock_db):
        """Test d'initialisation du service"""
        assert lpp_service.db == mock_db

    def test_create_act(self, lpp_service, mock_db, sample_lpp_act):
        """Test de création d'acte LPP"""
        # Mock des données d'entrée
        act_data = LPPActCreate(
            dossier_id=1,
            code_lpp="1234567890123",  # Code LPP valide (13 chiffres)
            denomination_libelle="Acte LPP de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

        # Mock de l'ajout en DB
        mock_db.get.return_value = Dossier(id=1)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 1))

        # Exécution
        result = lpp_service.create_act(act_data)

        # Vérifications
        assert isinstance(result, LPPActResponse)
        assert result.dossier_id == 1
        assert result.code_lpp == "1234567890123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_get_acts_by_dossier(self, lpp_service, mock_db, sample_lpp_act):
        """Test de récupération des actes LPP par dossier"""
        # Mock de la réponse
        expected_response = LPPActResponse(
            id=1,
            dossier_id=1,
            code_lpp="1234567890123",
            denomination_libelle="Acte LPP de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

        # Mock du service
        lpp_service.get_acts_by_dossier = Mock(return_value=[expected_response])

        # Exécution
        result = lpp_service.get_acts_by_dossier(1)

        # Vérifications
        assert len(result) == 1
        assert isinstance(result[0], LPPActResponse)
        assert result[0].id == 1

    def test_get_act_by_id(self, lpp_service, mock_db, sample_lpp_act):
        """Test de récupération d'un acte LPP par ID"""
        # Mock de la réponse
        expected_response = LPPActResponse(
            id=1,
            dossier_id=1,
            code_lpp="1234567890123",
            denomination_libelle="Acte LPP de test",
            execute_date=datetime.now(),
            prestataire_id=1,
            quantite=1,
            montant_unitaire_facture_ttc=100.0,
            commentaire="Test",
        )

        # Mock du service
        lpp_service.get_act_by_id = Mock(return_value=expected_response)

        # Exécution
        result = lpp_service.get_act_by_id(1)

        # Vérifications
        assert isinstance(result, LPPActResponse)
        assert result.id == 1

    def test_update_act(self, lpp_service, mock_db, sample_lpp_act):
        """Test de mise à jour d'acte LPP"""
        # Mock de récupération
        mock_db.get.return_value = sample_lpp_act

        # Données de mise à jour
        update_data = LPPActUpdate(
            denomination_libelle="Acte modifié",
            montant_unitaire_facture_ttc=150.0,
            commentaire="Test modifié",
        )

        # Mock de commit
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Exécution
        result = lpp_service.update_act(1, update_data)

        # Vérifications
        assert isinstance(result, LPPActResponse)
        assert result.denomination_libelle == "Acte modifié"
        assert result.montant_unitaire_facture_ttc == 150.0
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_delete_act(self, lpp_service, mock_db, sample_lpp_act):
        """Test de suppression d'acte LPP"""
        # Mock de récupération
        mock_db.get.return_value = sample_lpp_act

        # Mock de suppression
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        # Exécution
        lpp_service.delete_act(1)

        # Vérifications
        mock_db.delete.assert_called_once_with(sample_lpp_act)
        mock_db.commit.assert_called_once()
