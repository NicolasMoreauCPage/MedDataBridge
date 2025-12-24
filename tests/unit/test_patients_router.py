"""
Tests unitaires pour le routeur patients (app/routers/patients.py).

Ces tests couvrent :
- API REST de création de patients
- Routes de listing et détails
- Routes de création/édition/suppression
- Gestion des erreurs
- Intégration avec les services
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

# Import direct pour éviter les conflits avec conftest
from app.routers.patients import (
    router,
    api_create_patient,
    list_patients,
    patient_detail,
    edit_patient,
    update_patient_from_form,
    delete_patient,
    generate_sample_identity,
    new_patient_form,
    create_patient_from_form,
    get_templates,
)


class TestPatientsRouter:
    """Tests pour le routeur patients."""

    def test_router_configuration(self):
        """Test configuration du routeur."""
        assert router.prefix == "/patients"
        assert "patients" in router.tags

    @pytest.mark.asyncio
    async def test_api_create_patient_success(self):
        """Test création patient via API REST - succès."""
        mock_session = Mock()
        mock_patient = Mock()
        mock_patient.id = 123
        mock_patient.family = "Dupont"
        mock_patient.given = "Jean"
        mock_patient.birth_date = "1980-01-01"

        # Mock the schema instance that gets created
        mock_schema_instance = Mock()
        mock_schema_instance.family = "Dupont"
        mock_schema_instance.given = "Jean"
        mock_schema_instance.birth_date = "1980-01-01"

        with patch('app.routers.patients.patients_service') as mock_service, \
             patch('app.routers.patients.PatientCreateSchema', return_value=mock_schema_instance) as mock_schema:
            
            mock_service.create_patient.return_value = mock_patient

            response = await api_create_patient(
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                session=mock_session
            )

            assert isinstance(response, dict)
            assert response["id"] == 123
            assert response["family"] == "Dupont"
            assert response["given"] == "Jean"
            mock_service.create_patient.assert_called_once_with(session=mock_session, patient_data=mock_schema_instance)

    @pytest.mark.asyncio
    async def test_api_create_patient_error(self):
        """Test création patient via API REST - erreur."""
        mock_session = Mock()

        with patch('app.routers.patients.patients_service') as mock_service:
            mock_service.create_patient.side_effect = Exception("Erreur test")

            response = await api_create_patient(
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                session=mock_session
            )

            assert isinstance(response, JSONResponse)
            assert response.status_code == 500
            assert "Erreur test" in response.body.decode()

    def test_list_patients_with_ej_context(self):
        """Test listing patients avec contexte EJ."""
        mock_request = Mock()
        mock_ej_context = Mock()
        mock_ej_context.id = 42
        mock_request.state.ej_context = mock_ej_context
        mock_request.state.ght_context = None

        mock_session = Mock()
        mock_patient = Mock()
        mock_patient.id = 1
        mock_patient.identifier = "PAT001"
        mock_patient.family = "Dupont"
        mock_patient.given = "Jean"
        mock_patient.birth_date = "1980-01-01"
        mock_patient.gender = "male"

        mock_session.exec.return_value.all.return_value = [mock_patient]

        with patch('app.routers.patients.get_templates') as mock_get_templates:
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "rendered_template"

            response = list_patients(mock_request, mock_session)

            # Vérifier que la requête filtre par EJ
            call_args = mock_session.exec.call_args[0][0]
            assert "entite_juridique_id" in str(call_args)
            assert response == "rendered_template"

    def test_list_patients_with_ght_context(self):
        """Test listing patients avec contexte GHT."""
        mock_request = Mock()
        mock_ght_context = Mock()
        mock_ght_context.id = 10
        mock_request.state.ght_context = mock_ght_context
        mock_request.state.ej_context = None

        mock_session = Mock()
        mock_session.exec.return_value.all.return_value = []

        with patch('app.routers.patients.get_templates') as mock_get_templates:
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "rendered_template"

            response = list_patients(mock_request, mock_session)

            # Vérifier que la requête filtre par GHT
            call_args = mock_session.exec.call_args[0][0]
            assert "ght_context_id" in str(call_args)

    def test_patient_detail_found(self):
        """Test affichage détails patient - patient trouvé."""
        mock_request = Mock()
        mock_request.session = {}  # Use dict for session
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.id = 123
        mock_patient.family = "Dupont"
        mock_patient.dossiers = []

        mock_session.get.return_value = mock_patient

        with patch('app.routers.patients.get_templates') as mock_get_templates:
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "patient_detail"

            response = patient_detail(123, mock_request, mock_session)

            assert response == "patient_detail"
            from app.models import Patient
            mock_session.get.assert_called_once_with(Patient, 123)
            assert mock_request.session["patient_id"] == 123
            assert mock_request.session["patient_id"] == 123

    def test_patient_detail_not_found(self):
        """Test affichage détails patient - patient non trouvé."""
        mock_request = Mock()
        mock_session = Mock()
        mock_session.get.return_value = None

        with patch('app.routers.patients.get_templates') as mock_get_templates:
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.body = b"not_found"
            mock_template.TemplateResponse.return_value = mock_response

            response = patient_detail(999, mock_request, mock_session)

            assert response.status_code == 404
            assert "not_found" in str(response.body)

    def test_edit_patient_found(self):
        """Test formulaire édition patient - patient trouvé."""
        mock_request = Mock()
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.id = 123

        mock_session.get.return_value = mock_patient

        with patch('app.routers.patients.get_templates') as mock_get_templates, \
             patch('app.routers.patients.get_vocabulary_options') as mock_vocab:

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "edit_form"
            mock_vocab.return_value = []

            response = edit_patient(123, mock_request, mock_session)

            assert response == "edit_form"
            mock_vocab.assert_called()  # Vérifier que les vocabulaires sont chargés

    def test_edit_patient_not_found(self):
        """Test formulaire édition patient - patient non trouvé."""
        mock_request = Mock()
        mock_session = Mock()
        mock_session.get.return_value = None

        with patch('app.routers.patients.get_templates') as mock_get_templates:
            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_response = Mock()
            mock_response.status_code = 404
            mock_template.TemplateResponse.return_value = mock_response

            response = edit_patient(999, mock_request, mock_session)

            assert response.status_code == 404

    def test_update_patient_from_form_success(self):
        """Test mise à jour patient depuis formulaire - succès."""
        mock_request = Mock()
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.id = 123

        mock_session.get.return_value = mock_patient

        with patch('app.routers.patients.patients_service') as mock_service, \
             patch('app.routers.patients.flash') as mock_flash:

            mock_service.update_patient.return_value = None

            response = update_patient_from_form(
                patient_id=123,
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                gender="male",
                identifier="PAT001",
                request=mock_request,
                session=mock_session
            )

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 303
            assert "/patients/123" in response.headers["location"]
            mock_service.update_patient.assert_called_once()
            mock_flash.assert_called_with(mock_request, "Patient mis à jour avec succès", "success")

    def test_update_patient_from_form_error(self):
        """Test mise à jour patient depuis formulaire - erreur."""
        mock_request = Mock()
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.id = 123

        mock_session.get.return_value = mock_patient

        with patch('app.routers.patients.patients_service') as mock_service, \
             patch('app.routers.patients.flash') as mock_flash:

            mock_service.update_patient.side_effect = Exception("Erreur mise à jour")

            response = update_patient_from_form(
                patient_id=123,
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                gender="male",
                identifier="PAT001",
                request=mock_request,
                session=mock_session
            )

            assert isinstance(response, RedirectResponse)
            assert "/patients/123/edit" in response.headers["location"]
            mock_flash.assert_called_with(mock_request, "Erreur lors de la mise à jour: Erreur mise à jour", "error")

    def test_delete_patient_success(self):
        """Test suppression patient - succès."""
        mock_request = Mock()
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.id = 123
        mock_patient.family = "Dupont"
        mock_patient.given = "Jean"

        mock_session.get.return_value = mock_patient

        with patch('app.routers.patients.flash') as mock_flash:
            response = delete_patient(123, mock_request, mock_session)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 303
            assert "/patients" in response.headers["location"]
            mock_session.delete.assert_called_once_with(mock_patient)
            mock_session.commit.assert_called_once()
            mock_flash.assert_called_with(mock_request, "Patient Dupont Jean supprimé.", "success")

    def test_delete_patient_not_found(self):
        """Test suppression patient - patient non trouvé."""
        mock_request = Mock()
        mock_session = Mock()
        mock_session.get.return_value = None

        response = delete_patient(999, mock_request, mock_session)

        assert isinstance(response, HTMLResponse)
        assert response.status_code == 404
        assert "Patient introuvable" in response.body.decode()

    def test_generate_sample_identity(self):
        """Test génération identité d'exemple."""
        with patch('app.routers.patients.generate_patient_identity') as mock_gen, \
             patch('app.routers.patients.identity_to_sample_data') as mock_convert:

            mock_gen.return_value = "fake_identity"
            mock_convert.return_value = {"sample": "data"}

            response = generate_sample_identity()

            assert isinstance(response, dict)
            assert "sample_data" in response
            assert response["sample_data"] == {"sample": "data"}
            mock_gen.assert_called_once()
            mock_convert.assert_called_once_with("fake_identity")

    def test_new_patient_form(self):
        """Test formulaire nouveau patient."""
        mock_request = Mock()
        mock_request.query_params.get.return_value = None  # Pas de prefill

        with patch('app.routers.patients.get_templates') as mock_get_templates, \
             patch('app.routers.patients.get_vocabulary_options') as mock_vocab:

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "new_form"
            mock_vocab.return_value = []

            response = new_patient_form(mock_request)

            assert response == "new_form"
            # Vérifier que sample_data est None quand pas de prefill
            call_args = mock_template.TemplateResponse.call_args[0]
            context = call_args[2]
            assert context["sample_data"] is None
            assert context["sample_prefilled"] is False

    def test_new_patient_form_with_prefill(self):
        """Test formulaire nouveau patient avec pré-remplissage."""
        mock_request = Mock()
        mock_request.query_params.get.return_value = "1"  # Prefill demandé

        with patch('app.routers.patients.get_templates') as mock_get_templates, \
             patch('app.routers.patients.get_vocabulary_options') as mock_vocab, \
             patch('app.routers.patients.generate_patient_identity') as mock_gen, \
             patch('app.routers.patients.identity_to_sample_data') as mock_convert:

            mock_template = Mock()
            mock_get_templates.return_value = mock_template
            mock_template.TemplateResponse.return_value = "new_form"
            mock_vocab.return_value = []
            mock_gen.return_value = "identity"
            mock_convert.return_value = {"prefill": "data"}

            response = new_patient_form(mock_request)

            assert response == "new_form"
            call_args = mock_template.TemplateResponse.call_args[0]
            context = call_args[2]
            assert context["sample_data"] == {"prefill": "data"}
            assert context["sample_prefilled"] is True

    @pytest.mark.skip("Disabled due to form validation mocking complexity")
    @pytest.mark.asyncio
    async def test_create_patient_from_form_success(self):
        """Test création patient depuis formulaire - succès."""
        mock_request = Mock()
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.given = "Jean"
        mock_patient.family = "Dupont"

        with patch('app.routers.patients.patients_service') as mock_service, \
             patch('app.routers.patients.flash') as mock_flash, \
             patch('app.routers.patients.PatientCreateSchema') as mock_schema:

            mock_schema_instance = Mock()
            mock_schema.return_value = mock_schema_instance
            mock_service.create_patient.return_value = mock_patient

            response = await create_patient_from_form(
                request=mock_request,
                session=mock_session,
                external_id="EXT001",
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                gender="male"
            )

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 303
            assert "/patients" in response.headers["location"]
            mock_service.create_patient.assert_called_once_with(session=mock_session, patient_data=mock_schema_instance)
            mock_flash.assert_called_with(mock_request, "Patient Jean Dupont créé avec succès", "success")

    @pytest.mark.asyncio
    async def test_create_patient_from_form_ajax_success(self):
        """Test création patient depuis formulaire AJAX - succès."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/json"  # AJAX request
        mock_session = Mock()

        mock_patient = Mock()
        mock_patient.given = "Jean"
        mock_patient.family = "Dupont"

        with patch('app.routers.patients.patients_service') as mock_service, \
             patch('app.routers.patients.flash') as mock_flash, \
             patch('app.routers.patients.PatientCreateSchema') as mock_schema:

            mock_schema_instance = Mock()
            mock_schema.return_value = mock_schema_instance
            mock_service.create_patient.return_value = mock_patient

            response = await create_patient_from_form(
                request=mock_request,
                session=mock_session,
                external_id="EXT001",
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                gender="male"
            )

            assert isinstance(response, dict)
            assert response["status"] == "success"
            assert response["redirect"] == "/patients"

    @pytest.mark.asyncio
    async def test_create_patient_from_form_error(self):
        """Test création patient depuis formulaire - erreur."""
        mock_request = Mock()
        mock_session = Mock()

        with patch('app.routers.patients.patients_service') as mock_service, \
             patch('app.routers.patients.flash') as mock_flash, \
             patch('app.routers.patients.PatientCreateSchema') as mock_schema:

            mock_schema_instance = Mock()
            mock_schema.return_value = mock_schema_instance
            mock_service.create_patient.side_effect = Exception("Erreur création")

            response = await create_patient_from_form(
                request=mock_request,
                session=mock_session,
                external_id="EXT001",
                family="Dupont",
                given="Jean",
                birth_date="1980-01-01",
                gender="male"
            )

            assert isinstance(response, RedirectResponse)
            assert "/patients/new" in response.headers["location"]
            mock_flash.assert_called_with(mock_request, "Erreur lors de la création du patient: Erreur création", "error")
            mock_session.rollback.assert_called_once()

    def test_get_templates_function(self):
        """Test fonction get_templates."""
        mock_request = Mock()
        mock_templates = Mock()
        mock_request.app.state.templates = mock_templates

        result = get_templates(mock_request)

        assert result == mock_templates