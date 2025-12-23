"""Tests pour le router NGAP.

Ce module teste les fonctionnalités de gestion des actes NGAP,
y compris le dashboard, la consultation par dossier, et la création d'actes.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.models import Dossier, Patient, Venue, NGAPAct
from app.services.ngap_service import NGAPService


class TestNGAPRouter:
    """Tests pour le router NGAP."""

    @patch('app.routers.ngap.templates.TemplateResponse')
    def test_ngap_dashboard(self, mock_template, client: TestClient):
        """Test affichage dashboard NGAP."""
        response = client.get("/ngap/")

        assert response.status_code == 200
        mock_template.assert_called_once_with("ngap/dashboard.html", {
            "request": mock_template.call_args[0][1]["request"],
            "title": "Gestion NGAP"
        })

    @patch('app.routers.ngap.templates.TemplateResponse')
    def test_ngap_by_dossier_success(self, mock_template, session: Session, client: TestClient):
        """Test consultation actes NGAP d'un dossier existant."""
        # Créer les données de test
        patient = Patient(
            id=1,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=1,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=1,
            admit_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        session.add(patient)
        session.add(dossier)
        session.commit()

        # Mock du service NGAP
        with patch('app.routers.ngap.NGAPService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.get_acts_by_dossier = AsyncMock(return_value=[
                {"id": 1, "lettre_cle": "C", "coefficient": 1.0}
            ])

            response = client.get("/ngap/dossier/1")

            assert response.status_code == 200
            mock_template.assert_called_once()
            call_args = mock_template.call_args
            assert call_args[0][0] == "ngap/dossier_acts.html"
            # Check that the dossier passed to template has the correct id
            template_dossier = call_args[0][1]["dossier"]
            assert template_dossier.id == dossier.id
            assert template_dossier.patient_id == dossier.patient_id
            assert call_args[0][1]["acts"] == [{"id": 1, "lettre_cle": "C", "coefficient": 1.0}]
            assert f"NGAP - Dossier #{template_dossier.dossier_seq}" == call_args[0][1]["title"]

    def test_ngap_by_dossier_not_found(self, client: TestClient):
        """Test consultation actes NGAP d'un dossier inexistant."""
        response = client.get("/ngap/dossier/999")

        assert response.status_code == 404
        assert "Dossier non trouvé" in response.json()["detail"]

    @patch('app.routers.ngap.templates.TemplateResponse')
    def test_create_ngap_form_success(self, mock_template, session: Session, client: TestClient):
        """Test affichage formulaire création acte NGAP."""
        # Créer les données de test
        patient = Patient(
            id=1,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=1,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=1,
            admit_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        session.add(patient)
        session.add(dossier)
        session.commit()

        response = client.get("/ngap/create/1")

        assert response.status_code == 200
        mock_template.assert_called_once_with("ngap/create_form.html", {
            "request": mock_template.call_args[0][1]["request"],
            "dossier": dossier,
            "title": "Nouveau NGAP - Dossier #1001"
        })

    def test_create_ngap_form_dossier_not_found(self, client: TestClient):
        """Test affichage formulaire avec dossier inexistant."""
        response = client.get("/ngap/create/999")

        assert response.status_code == 404
        assert "Dossier non trouvé" in response.json()["detail"]

    @patch('app.routers.ngap.templates.TemplateResponse')
    def test_create_ngap_act_success(self, mock_template, session: Session, client: TestClient):
        """Test création acte NGAP réussie."""
        # Créer les données de test
        patient = Patient(
            id=1,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=1,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=1,
            admit_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        session.add(patient)
        session.add(dossier)
        session.commit()

        # Mock du service NGAP
        with patch('app.routers.ngap.NGAPService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.create_act = AsyncMock(return_value=Mock(
                id=1,
                lettre_cle="C",
                coefficient=1.5,
                execute_date=datetime(2024, 1, 15, 14, 30)
            ))

            # Données du formulaire
            form_data = {
                "lettre_cle": "C",
                "coefficient": "1.5",
                "execute_date": "2024-01-15T14:30:00",
                "prestataire_id": "1",
                "denombrement": "1",
                "position_dentaire": "11",
                "execute_heure": "14:30",
                "numero_seance": "1",
                "montant": "25.50",
                "commentaire": "Test acte"
            }

            response = client.post("/ngap/create/1", data=form_data)

            assert response.status_code == 200
            mock_service.create_act.assert_called_once()
            call_args = mock_service.create_act.call_args[0][0]
            assert call_args["dossier_id"] == 1
            assert call_args["lettre_cle"] == "C"
            assert call_args["coefficient"] == 1.5
            assert call_args["execute_date"] == datetime(2024, 1, 15, 14, 30)
            assert call_args["prestataire_id"] == 1
            assert call_args["denombrement"] == 1
            assert call_args["position_dentaire"] == "11"
            assert call_args["execute_heure"] == "14:30"
            assert call_args["numero_seance"] == 1
            assert call_args["montant"] == 25.5
            assert call_args["commentaire"] == "Test acte"

            mock_template.assert_called_once_with("ngap/act_created.html", {
                "request": mock_template.call_args[0][1]["request"],
                "act": mock_service.create_act.return_value,
                "title": "Acte NGAP créé"
            })

    def test_create_ngap_act_invalid_date(self, session: Session, client: TestClient):
        """Test création acte NGAP avec date invalide."""
        # Créer les données de test
        patient = Patient(
            id=1,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=1,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=1,
            admit_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        session.add(patient)
        session.add(dossier)
        session.commit()

        form_data = {
            "lettre_cle": "C",
            "coefficient": "1.5",
            "execute_date": "invalid-date",  # Date invalide
        }

        response = client.post("/ngap/create/1", data=form_data)

        assert response.status_code == 400
        assert "Date invalide" in response.json()["detail"]

    def test_create_ngap_act_missing_required_fields(self, session: Session, client: TestClient):
        """Test création acte NGAP avec champs requis manquants."""
        # Créer les données de test
        patient = Patient(
            id=1,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=1,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=1,
            admit_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        session.add(patient)
        session.add(dossier)
        session.commit()

        # Données incomplètes (lettre_cle manquant)
        form_data = {
            "coefficient": "1.5",
            "execute_date": "2024-01-15T14:30:00",
        }

        response = client.post("/ngap/create/1", data=form_data)

        # FastAPI devrait retourner une erreur 422 pour les champs requis manquants
        assert response.status_code == 422

    def test_create_ngap_act_dossier_not_found(self, client: TestClient):
        """Test création acte NGAP avec dossier inexistant."""
        form_data = {
            "lettre_cle": "C",
            "coefficient": "1.5",
            "execute_date": "2024-01-15T14:30:00",
        }

        response = client.post("/ngap/create/999", data=form_data)

        assert response.status_code == 404
        assert "Dossier non trouvé" in response.json()["detail"]