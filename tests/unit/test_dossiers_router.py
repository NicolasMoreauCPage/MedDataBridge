"""
Tests unitaires pour le routeur dossiers (app/routers/dossiers.py).

Ces tests couvrent :
- Routes de listing et détails des dossiers
- Routes de création/édition/suppression
- API REST endpoints
- Gestion des contextes GHT/EJ
- Gestion des erreurs
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

# Import direct pour éviter les conflits
from app.routers.dossiers import (
    router,
    public_router,
    api_router,
    list_dossiers,
    show_dossier,
    redirect_dossier_cotation,
    new_dossier,
    create_dossier,
    edit_dossier,
    update_dossier,
    delete_dossier,
    api_list_dossiers,
    api_search_dossiers,
    api_get_dossier,
    api_create_dossier,
    get_templates_with_filters,
)


class TestDossiersRouter(unittest.TestCase):
    """Tests pour le routeur dossiers."""

    def test_router_configurations(self):
        """Test configurations des routeurs."""
        assert router.prefix == "/dossiers"
        assert "dossiers" in router.tags

        assert public_router.prefix == "/dossiers"
        assert "dossiers-public" in public_router.tags

        assert api_router.prefix == "/dossiers/api"
        assert "dossiers-api" in api_router.tags

    def test_list_dossiers_basic(self):
        """Test listing dossiers - cas de base."""
        mock_request = Mock()
        mock_session = Mock()

        # Mock du contexte EJ
        mock_ej_context = Mock()
        mock_ej_context.id = 42
        mock_request.state.ej_context = mock_ej_context

        # Mock des dossiers retournés par le service
        mock_dossier = Mock()
        mock_dossier.dossier_seq = 12345
        mock_dossier.id = 1
        mock_dossier.patient_id = 100
        mock_dossier.venues = [Mock()]
        mock_dossier.venues[0].uf_responsabilite = "CARDIO"
        mock_dossier.dossier_type = Mock()
        mock_dossier.dossier_type.value = "hospitalise"
        mock_dossier.admit_time = datetime(2023, 12, 1, 10, 0)
        mock_dossier.discharge_time = None

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates:

            mock_service.get_dossiers.return_value = [mock_dossier]
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "rendered_list"

            response = list_dossiers(mock_request, patient_id=None, dossier_type=None, dossier_seq=None, session=mock_session)

            assert response == "rendered_list"
            mock_service.get_dossiers.assert_called_once_with(
                mock_session, ej_id=42, patient_id=None,
                dossier_type=None, dossier_seq=None
            )

    def test_list_dossiers_with_filters(self):
        """Test listing dossiers avec filtres."""
        mock_request = Mock()
        mock_session = Mock()
        mock_request.state.ej_context = None

        from app.models import DossierType
        dossier_type = DossierType.URGENCE

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates:

            mock_service.get_dossiers.return_value = []
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "rendered_list"

            response = list_dossiers(
                mock_request,
                patient_id=100,
                dossier_type=dossier_type,
                dossier_seq=12345,
                session=mock_session
            )

            assert response == "rendered_list"
            mock_service.get_dossiers.assert_called_once_with(
                mock_session, ej_id=None, patient_id=100,
                dossier_type=dossier_type, dossier_seq=12345
            )

    def test_show_dossier_found(self):
        """Test affichage dossier - trouvé."""
        mock_request = Mock()
        mock_session = Mock()

        # Assurer qu'il n'y a pas de ght_context
        mock_request.state.ght_context = None

        # Mock du dossier
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_dossier.patient_id = 456
        mock_dossier.entite_juridique_id = None

        # Mock du patient
        mock_patient = Mock()
        mock_patient.family = "Dupont"
        mock_patient.given = "Jean"

        # Mock des venues
        mock_venue = Mock()
        mock_venue.start_time = datetime(2023, 12, 1, 10, 0)

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates, \
             patch('app.db.session_factory') as mock_session_factory:

            mock_service.get_dossier.return_value = mock_dossier
            mock_session_factory.return_value = mock_session

            # Mock des requêtes SQLAlchemy
            mock_patient_query = Mock()
            mock_patient_query.first.return_value = mock_patient
            
            # Mock des venues
            mock_venue_query = Mock()
            mock_venue_query.all.return_value = [mock_venue]
            
            mock_session.exec.side_effect = [mock_patient_query, mock_venue_query]

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "dossier_detail"

            response = show_dossier(123, mock_request)

            assert response == "dossier_detail"
            mock_service.get_dossier.assert_called_once_with(mock_session, 123)

    def test_show_dossier_not_found(self):
        """Test affichage dossier - non trouvé."""
        mock_request = Mock()

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates, \
             patch('app.db.session_factory') as mock_session_factory:

            mock_service.get_dossier.return_value = None
            mock_session_factory.return_value = Mock()

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = HTMLResponse("Not found", status_code=404)

            response = show_dossier(999, mock_request)

            assert isinstance(response, HTMLResponse)
            assert response.status_code == 404

    def test_redirect_dossier_cotation(self):
        """Test redirection vers cotation."""
        response = redirect_dossier_cotation(123)

        assert isinstance(response, RedirectResponse)
        assert response.status_code == 302
        assert "/cotation-modern?dossier_id=123" in response.headers["location"]

    def test_new_dossier_with_patient_context(self):
        """Test formulaire nouveau dossier avec contexte patient."""
        mock_request = Mock()
        mock_session = Mock()

        # Mock du contexte patient
        mock_patient = Mock()
        mock_patient.id = 456
        mock_request.state.patient_context = mock_patient
        mock_request.state.ej_context = None

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates, \
             patch('os.getenv') as mock_getenv:

            mock_service.get_uf_options.return_value = []
            mock_getenv.return_value = None  # Pas en mode test

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "new_form"

            response = new_dossier(mock_request, session=mock_session)

            assert response == "new_form"

    def test_new_dossier_without_patient_context(self):
        """Test formulaire nouveau dossier sans contexte patient."""
        mock_request = Mock()
        mock_session = Mock()

        mock_request.state.patient_context = None
        mock_request.query_params.get.return_value = None

        response = new_dossier(mock_request, session=mock_session)

        assert isinstance(response, RedirectResponse)
        assert "/patients" in response.headers["location"]

    def test_create_dossier_success(self):
        """Test création dossier - succès."""
        mock_request = Mock()
        mock_session = Mock()

        # Mock du contexte patient
        mock_patient = Mock()
        mock_request.state.patient_context = mock_patient

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.flash') as mock_flash:

            mock_service.create_dossier_with_pre_admit_venue.return_value = Mock()

            response = create_dossier(
                mock_request,
                uf_responsabilite="CARDIO",
                dossier_type="hospitalise",
                admission_source="urgence",
                attending_provider="Dr. Smith",
                admit_time="2023-12-01T10:00:00",
                current_state="Hospitalisé",
                session=mock_session
            )

            assert isinstance(response, RedirectResponse)
            assert "/dossiers" in response.headers["location"]
            mock_service.create_dossier_with_pre_admit_venue.assert_called_once()
            mock_flash.assert_called_with(mock_request, "Dossier et pré-admission créés avec succès.", "success")

    def test_create_dossier_without_patient_context(self):
        """Test création dossier sans contexte patient."""
        mock_request = Mock()
        mock_session = Mock()

        mock_request.state.patient_context = None

        with patch('app.routers.dossiers.flash') as mock_flash:
            response = create_dossier(
                mock_request,
                uf_responsabilite="CARDIO",
                dossier_type="hospitalise",
                admission_source="urgence",
                attending_provider="Dr. Smith",
                admit_time="2023-12-01T10:00:00",
                current_state="Hospitalisé",
                session=mock_session
            )

            assert isinstance(response, RedirectResponse)
            assert "/patients" in response.headers["location"]
            mock_flash.assert_called_with(mock_request, "Aucun patient sélectionné.", "error")

    def test_edit_dossier_found(self):
        """Test formulaire édition dossier - trouvé."""
        mock_request = Mock()
        mock_session = Mock()

        # Mock du dossier
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_dossier.patient_id = 456
        mock_dossier.dossier_type.value = "hospitalise"
        mock_dossier.admit_time = datetime(2023, 12, 1, 10, 0)
        mock_dossier.dossier_seq = 789

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates:

            mock_service.get_dossier.return_value = mock_dossier

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "edit_form"

            response = edit_dossier(123, mock_request, mock_session)

            assert response == "edit_form"
            mock_service.get_dossier.assert_called_once_with(mock_session, 123)

    def test_edit_dossier_not_found(self):
        """Test formulaire édition dossier - non trouvé."""
        mock_request = Mock()
        mock_session = Mock()

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates:

            mock_service.get_dossier.return_value = None

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = HTMLResponse("Not found", status_code=404)

            response = edit_dossier(999, mock_request, mock_session)

            assert isinstance(response, HTMLResponse)
            assert response.status_code == 404

    def test_update_dossier_success(self):
        """Test mise à jour dossier - succès."""
        mock_request = Mock()
        mock_session = Mock()

        # Mock du dossier existant
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_session.get.return_value = mock_dossier

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.flash') as mock_flash:

            response = update_dossier(
                mock_request,
                dossier_id=123,
                patient_id=456,
                uf_responsabilite="CARDIO",
                dossier_type="hospitalise",
                admission_source="urgence",
                attending_provider="Dr. Smith",
                admit_time="2023-12-01T10:00:00",
                dossier_seq=789,
                session=mock_session
            )

            assert isinstance(response, RedirectResponse)
            assert "/dossiers/123" in response.headers["location"]
            mock_service.update_dossier.assert_called_once()
            mock_flash.assert_called_with(mock_request, "Dossier mis à jour avec succès.", "success")

    def test_update_dossier_not_found(self):
        """Test mise à jour dossier - non trouvé."""
        mock_request = Mock()
        mock_session = Mock()

        mock_session.get.return_value = None

        with patch('app.routers.dossiers.flash') as mock_flash:
            response = update_dossier(
                mock_request,
                dossier_id=999,
                patient_id=456,
                uf_responsabilite="CARDIO",
                dossier_type="hospitalise",
                admission_source="urgence",
                attending_provider="Dr. Smith",
                admit_time="2023-12-01T10:00:00",
                dossier_seq=789,
                session=mock_session
            )

            assert isinstance(response, RedirectResponse)
            assert "/dossiers" in response.headers["location"]
            mock_flash.assert_called_with(mock_request, "Dossier introuvable.", "error")

    def test_delete_dossier_success(self):
        """Test suppression dossier - succès."""
        mock_request = Mock()
        mock_session = Mock()

        # Mock du dossier
        mock_dossier = Mock()

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.flash') as mock_flash:

            mock_service.get_dossier.return_value = mock_dossier

            response = delete_dossier(123, mock_request, mock_session)

            assert isinstance(response, RedirectResponse)
            assert "/dossiers" in response.headers["location"]
            mock_service.delete_dossier.assert_called_once_with(mock_session, mock_dossier)
            mock_flash.assert_called_with(mock_request, "Dossier supprimé.", "success")

    def test_delete_dossier_not_found(self):
        """Test suppression dossier - non trouvé."""
        mock_request = Mock()
        mock_session = Mock()

        with patch('app.routers.dossiers.dossiers_service') as mock_service, \
             patch('app.routers.dossiers.get_templates_with_filters') as mock_get_templates:

            mock_service.get_dossier.return_value = None

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = HTMLResponse("Not found", status_code=404)

            response = delete_dossier(999, mock_request, mock_session)

            assert isinstance(response, HTMLResponse)
            assert response.status_code == 404

    def test_api_list_dossiers(self):
        """Test API listing dossiers."""
        mock_session = Mock()

        # Mock des dossiers
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_dossier.patient_id = 456
        mock_dossier.dossier_type = None
        mock_dossier.admit_time = datetime(2023, 12, 1, 10, 0)
        mock_dossier.discharge_time = None

        with patch('app.routers.dossiers.dossiers_service') as mock_service:
            mock_service.get_dossiers.return_value = [mock_dossier]

            response = api_list_dossiers(mock_session)

            assert isinstance(response, list)
            assert len(response) == 1
            assert response[0]["id"] == 123
            assert response[0]["patient_id"] == 456

    def test_api_search_dossiers(self):
        """Test API recherche dossiers."""
        mock_session = Mock()

        # Mock des dossiers avec patient
        mock_patient = Mock()
        mock_patient.family = "Dupont"
        mock_patient.given = "Jean"

        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_dossier.dossier_seq = 456
        mock_dossier.patient = mock_patient
        mock_dossier.admit_time = datetime(2023, 12, 1, 10, 0)
        mock_dossier.medecin_responsable = None
        mock_dossier.current_state = "Hospitalisé"

        # Mock de la requête SQLAlchemy
        mock_result = Mock()
        mock_result.all.return_value = [mock_dossier]
        mock_session.exec.return_value = mock_result

        response = api_search_dossiers("Dupont", 10, mock_session)

        assert isinstance(response, list)
        assert len(response) == 1
        assert response[0]["id"] == 123
        assert response[0]["patient"]["family"] == "Dupont"

    def test_api_get_dossier_found(self):
        """Test API récupération dossier - trouvé."""
        mock_session = Mock()

        # Mock du patient
        mock_patient = Mock()
        mock_patient.family = "Dupont"
        mock_patient.given = "Jean"
        mock_patient.birth_date = datetime(1980, 5, 15).date()

        # Mock du médecin
        mock_medecin = Mock()
        mock_medecin.nom = "Smith"
        mock_medecin.prenom = "John"

        # Mock du dossier
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_dossier.dossier_seq = 456
        mock_dossier.patient = mock_patient
        mock_dossier.admit_time = datetime(2023, 12, 1, 10, 0)
        mock_dossier.discharge_time = None
        mock_dossier.dossier_type = None
        mock_dossier.medecin_responsable = mock_medecin
        mock_dossier.current_state = "Hospitalisé"
        mock_dossier.uf_responsabilite = "CARDIO"

        # Mock de la requête SQLAlchemy
        mock_result = Mock()
        mock_result.first.return_value = mock_dossier
        mock_session.exec.return_value = mock_result

        response = api_get_dossier(123, mock_session)

        assert isinstance(response, dict)
        assert response["id"] == 123
        assert response["dossier_seq"] == 456
        assert response["patient"]["family"] == "Dupont"
        assert response["medecin_responsable"]["nom"] == "Smith"

    def test_api_get_dossier_not_found(self):
        """Test API récupération dossier - non trouvé."""
        mock_session = Mock()

        # Mock de la requête SQLAlchemy
        mock_result = Mock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        response = api_get_dossier(999, mock_session)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_api_create_dossier_success(self):
        """Test API création dossier - succès."""
        mock_session = Mock()

        # Mock du patient
        mock_patient = Mock()
        mock_session.get.return_value = mock_patient

        with patch('app.routers.dossiers.dossiers_service') as mock_service:
            mock_service.create_dossier_with_pre_admit_venue.return_value = Mock(id=123, dossier_seq=456)

            response = await api_create_dossier(
                patient_id=100,
                dossier_type="hospitalise",
                admit_time="2023-12-01T10:00:00",
                uf_responsabilite="CARDIO",
                session=mock_session
            )

            assert isinstance(response, dict)
            assert response["id"] == 123
            assert response["dossier_seq"] == 456
            mock_service.create_dossier_with_pre_admit_venue.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_create_dossier_patient_not_found(self):
        """Test API création dossier - patient non trouvé."""
        mock_session = Mock()
        mock_session.get.return_value = None

        response = await api_create_dossier(
            patient_id=999,
            dossier_type="hospitalise",
            admit_time="2023-12-01T10:00:00",
            session=mock_session
        )

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert "Patient not found" in response.body.decode()

    def test_get_templates_with_filters(self):
        """Test fonction get_templates_with_filters."""
        mock_request = Mock()
        mock_templates = Mock()
        mock_request.app.state.templates = mock_templates

        result = get_templates_with_filters(mock_request)

        assert result == mock_templates