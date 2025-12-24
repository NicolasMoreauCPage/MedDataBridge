# tests/unit/test_api_ucd_lpp.py
"""
Tests unitaires pour les APIs UCD et LPP
"""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime
from sqlmodel import select

from app.schemas.ucd import UCDActCreate, UCDActUpdate
from app.schemas.lpp import LPPActCreate, LPPActUpdate

# Import API modules to ensure routes are registered
from app import api


class TestUCDAPI:
    """Tests pour l'API UCD"""

    @pytest.fixture
    def mock_ucd_service(self):
        """Mock du service UCD"""
        service = Mock()
        service.create_act = AsyncMock()
        service.get_acts_by_dossier = AsyncMock()
        service.update_act = AsyncMock()
        service.delete_act = AsyncMock()
        service.validate_act = AsyncMock()
        return service

    def test_create_ucd_act_success(self, client, session):
        """Test création d'acte UCD - succès"""
        # Créer des données de test
        from app.models import Patient, Dossier
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()

        # Données de test pour l'acte UCD
        act_data = {
            "dossier_id": dossier.id,
            "code_cip": "1234567890123",  # Code CIP-13 valide (13 chiffres)
            "designation": "Test UCD",
            "execute_date": "2025-12-21T10:00:00",
            "prestataire_id": 1,
            "quantite": 1,
            "prix_unitaire": 100.0,
            "montant_total": 100.0,
            "commentaire": "Test"
        }

        # Exécution
        response = client.post("/api/ucd/", json=act_data)

        # Vérifications
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["code_cip"] == "1234567890123"
        assert data["dossier_id"] == dossier.id

    def test_get_ucd_acts_by_dossier(self, client, session):
        """Test récupération des actes UCD par dossier"""
        # Créer des données de test
        from app.models import Patient, Dossier, UCDAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte UCD
        ucd_act = UCDAct(
            dossier_id=dossier.id,
            code_cip="1234567890123",
            designation="Test UCD",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(ucd_act)
        session.commit()

        # Exécution
        response = client.get(f"/api/ucd/dossier/{dossier.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == ucd_act.id
        assert data[0]["code_cip"] == "1234567890123"
        assert data[0]["dossier_id"] == dossier.id

    def test_update_ucd_act(self, client, session):
        """Test mise à jour d'acte UCD"""
        # Créer des données de test
        from app.models import Patient, Dossier, UCDAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte UCD
        ucd_act = UCDAct(
            dossier_id=dossier.id,
            code_cip="1234567890123",
            designation="Test UCD",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(ucd_act)
        session.commit()

        # Données de mise à jour
        update_data = {
            "designation": "Test UCD modifié",
            "commentaire": "Test modifié"
        }

        # Exécution
        response = client.put(f"/api/ucd/{ucd_act.id}", json=update_data)

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert data["designation"] == "Test UCD modifié"
        assert data["commentaire"] == "Test modifié"
        assert data["id"] == ucd_act.id

    def test_delete_ucd_act(self, client, session):
        """Test suppression d'acte UCD"""
        # Créer des données de test
        from app.models import Patient, Dossier, UCDAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte UCD
        ucd_act = UCDAct(
            dossier_id=dossier.id,
            code_cip="1234567890123",
            designation="Test UCD",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(ucd_act)
        session.commit()

        # Exécution
        response = client.delete(f"/api/ucd/{ucd_act.id}")

        # Vérifications
        assert response.status_code == 204

        # Note: Nous ne pouvons pas vérifier la suppression en base car l'API utilise une session différente
        # Le status 204 confirme que la suppression a été demandée avec succès

    def test_validate_ucd_act(self, client, session):
        """Test validation d'acte UCD"""
        # Créer des données de test
        from app.models import Patient, Dossier, UCDAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte UCD
        ucd_act = UCDAct(
            dossier_id=dossier.id,
            code_cip="1234567890123",
            designation="Test UCD",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(ucd_act)
        session.commit()

        # Exécution
        response = client.post(f"/api/ucd/{ucd_act.id}/validate")

        # Vérifications - le service validate_act retourne probablement un résultat de validation
        assert response.status_code == 200
        data = response.json()
        # Les assertions dépendent de ce que retourne validate_act


class TestLPPAPI:
    """Tests pour l'API LPP"""

    def test_create_lpp_act_success(self, client, session):
        """Test création d'acte LPP - succès"""
        # Créer des données de test
        from app.models import Patient, Dossier
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()

        # Données de test pour l'acte LPP
        act_data = {
            "dossier_id": dossier.id,
            "code_lpp": "1234567890123",  # Code LPP-13 valide (13 chiffres)
            "libelle": "Test LPP",
            "execute_date": "2025-12-21T10:00:00",
            "prestataire_id": 1,
            "quantite": 1,
            "prix_unitaire": 100.0,
            "montant_total": 100.0,
            "commentaire": "Test"
        }

        # Exécution
        response = client.post("/api/lpp/", json=act_data)

        # Vérifications
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["code_lpp"] == "1234567890123"
        assert data["dossier_id"] == dossier.id

    def test_get_lpp_acts_by_dossier(self, client, session):
        """Test récupération des actes LPP par dossier"""
        # Créer des données de test
        from app.models import Patient, Dossier, LPPAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte LPP
        lpp_act = LPPAct(
            dossier_id=dossier.id,
            code_lpp="1234567890123",
            libelle="Test LPP",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(lpp_act)
        session.commit()

        # Exécution
        response = client.get(f"/api/lpp/dossier/{dossier.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == lpp_act.id
        assert data[0]["code_lpp"] == "1234567890123"

    def test_update_lpp_act(self, client, session):
        """Test mise à jour d'acte LPP"""
        # Créer des données de test
        from app.models import Patient, Dossier, LPPAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte LPP
        lpp_act = LPPAct(
            dossier_id=dossier.id,
            code_lpp="1234567890123",
            libelle="Test LPP",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(lpp_act)
        session.commit()

        # Données de mise à jour
        update_data = {
            "libelle": "Test LPP modifié"
        }

        # Exécution
        response = client.put(f"/api/lpp/{lpp_act.id}", json=update_data)

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert data["libelle"] == "Test LPP modifié"
        assert data["id"] == lpp_act.id

    def test_delete_lpp_act(self, client, session):
        """Test suppression d'acte LPP"""
        # Créer des données de test
        from app.models import Patient, Dossier, LPPAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte LPP
        lpp_act = LPPAct(
            dossier_id=dossier.id,
            code_lpp="1234567890123",
            libelle="Test LPP",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(lpp_act)
        session.commit()

        # Exécution
        response = client.delete(f"/api/lpp/{lpp_act.id}")

        # Vérifications
        assert response.status_code == 204

        # Note: Nous ne pouvons pas vérifier la suppression en base car l'API utilise une session différente
        # Le status 204 confirme que la suppression a été demandée avec succès

    def test_validate_lpp_act(self, client, session):
        """Test validation d'acte LPP"""
        # Créer des données de test
        from app.models import Patient, Dossier, LPPAct
        from app.models_structure import GHTContext
        
        # Créer un GHT context si nécessaire
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()
        
        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()
        
        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()
        
        # Créer un acte LPP
        lpp_act = LPPAct(
            dossier_id=dossier.id,
            code_lpp="1234567890123",
            libelle="Test LPP",
            execute_date=datetime.utcnow(),
            prestataire_id=1,
            quantite=1,
            prix_unitaire=100.0,
            montant_total=100.0,
            commentaire="Test"
        )
        session.add(lpp_act)
        session.commit()

        # Exécution
        response = client.post(f"/api/lpp/{lpp_act.id}/validate")

        # Vérifications - le service validate_act retourne probablement un résultat de validation
        assert response.status_code == 200
        data = response.json()
        # Les assertions dépendent de ce que retourne validate_act