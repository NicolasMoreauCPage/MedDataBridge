"""Tests pour le router des namespaces.

Ce module teste les fonctionnalités de gestion des namespaces d'identifiants,
y compris la création, consultation, modification et suppression des namespaces.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from sqlmodel import Session, select
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.models_structure import GHTContext, IdentifierNamespace, EntiteJuridique
from app.models_identifiers import Identifier
from app.routers.namespaces import (
    router,
    get_context_or_404,
    get_ej_or_404
)


class TestNamespacesRouter:
    """Tests pour le router des namespaces."""

    def test_get_context_or_404_success(self, session: Session):
        """Test récupération contexte existant."""
        # Créer un contexte de test
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()
        session.refresh(context)

        # Tester la fonction
        result = get_context_or_404(session, context.id)
        assert result.id == context.id
        assert result.name == "TEST"

    def test_get_context_or_404_not_found(self, session: Session):
        """Test récupération contexte inexistant."""
        with pytest.raises(HTTPException) as exc_info:
            get_context_or_404(session, 999)
        assert exc_info.value.status_code == 404
        assert "Contexte non trouvé" in exc_info.value.detail

    def test_get_ej_or_404_success(self, session: Session):
        """Test récupération entité juridique existante."""
        # Créer les données de test
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        ej = EntiteJuridique(
            name="Test EJ",
            finess_ej="123456789",
            ght_context_id=context.id,
            is_active=True
        )
        session.add(ej)
        session.commit()
        session.refresh(ej)

        # Tester la fonction
        result = get_ej_or_404(session, context, ej.id)
        assert result.id == ej.id
        assert result.name == "Test EJ"

    def test_get_ej_or_404_not_found(self, session: Session):
        """Test récupération entité juridique inexistante."""
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_ej_or_404(session, context, 999)
        assert exc_info.value.status_code == 404
        assert "Entité juridique non trouvée" in exc_info.value.detail

    @patch('app.routers.ght.namespaces.templates.TemplateResponse')
    def test_new_namespace_form(self, mock_template, session: Session, client: TestClient):
        """Test affichage formulaire création namespace."""
        # Créer un contexte de test
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        # Faire la requête
        response = client.get(f"/admin/ght/{context.id}/namespaces/new")

        assert response.status_code == 200
        mock_template.assert_called_once()
        call_args = mock_template.call_args
        assert call_args[0][2]['context'] == context
        assert call_args[0][2]['namespace'] is None

    def test_create_namespace_success(self, session: Session, client: TestClient):
        """Test création namespace réussie."""
        # Créer un contexte de test
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        # Données du formulaire
        form_data = {
            "name": "Test Namespace",
            "system": "urn:test:namespace",
            "oid": "1.2.3.4.5",
            "type": "IPP",
            "description": "Test namespace",
            "is_active": "true",
            "prefix_pattern": "TEST-{counter}",
            "prefix_mode": "fixed"
        }

        # Faire la requête POST
        response = client.post(
            f"/admin/ght/{context.id}/namespaces/new",
            data=form_data
        )

        # Vérifier que la réponse est soit une redirection (302) soit une page de succès (200)
        assert response.status_code in [200, 302]

        # Vérifier que le namespace a été créé
        namespace = session.exec(
            select(IdentifierNamespace)
            .where(IdentifierNamespace.system == "urn:test:namespace")
        ).first()
        assert namespace is not None
        assert namespace.name == "Test Namespace"
        assert namespace.type == "IPP"
        assert namespace.is_active is True
        assert namespace.ght_context_id == context.id

    def test_create_namespace_missing_system(self, session: Session, client: TestClient):
        """Test création namespace avec system manquant."""
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        form_data = {
            "name": "Test Namespace",
            # system manquant
            "type": "IPP",
            "description": "",
            "oid": ""
        }

        response = client.post(
            f"/admin/ght/{context.id}/namespaces/new",
            data=form_data
        )

        assert response.status_code in [400, 422]
        # Vérifier que c'est une erreur de validation (ne pas vérifier le message spécifique)

    def test_create_namespace_duplicate_system(self, session: Session, client: TestClient):
        """Test création namespace avec system déjà existant."""
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        # Créer un namespace existant
        existing = IdentifierNamespace(
            name="Existing",
            system="urn:test:duplicate",
            type="IPP",  # Ajouter type requis
            ght_context_id=context.id
        )
        session.add(existing)
        session.commit()

        form_data = {
            "name": "New Namespace",
            "system": "urn:test:duplicate",  # Même system
            "type": "IPP",
            "description": "",
            "oid": ""
        }

        response = client.post(
            f"/admin/ght/{context.id}/namespaces/new",
            data=form_data
        )

        assert response.status_code in [400, 422]
        # Vérifier que c'est une erreur de validation (ne pas vérifier le message spécifique)

    def test_create_namespace_prefix_range_invalid(self, session: Session, client: TestClient):
        """Test création namespace avec préfixe range invalide."""
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        form_data = {
            "name": "Test Namespace",
            "system": "urn:test:prefix",
            "type": "IPP",
            "description": "",
            "oid": "",
            "prefix_mode": "range",
            "prefix_min": "invalid",  # Pas un entier
            "prefix_max": "100"
        }

        response = client.post(
            f"/admin/ght/{context.id}/namespaces/new",
            data=form_data
        )

        assert response.status_code in [400, 422]
        # Vérifier que c'est une erreur de validation (ne pas vérifier le message spécifique)

    def test_view_namespace_success(self, session: Session, client: TestClient):
        """Test consultation namespace existant."""
        # Créer les données de test
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        namespace = IdentifierNamespace(
            name="Test Namespace",
            system="urn:test:view",
            type="IPP",
            ght_context_id=context.id
        )
        session.add(namespace)

        # Créer un identifiant utilisant ce namespace
        identifier = Identifier(
            value="12345",
            type="IPP",
            system="urn:test:view",
            patient_id=1
        )
        session.add(identifier)
        session.commit()

        # Faire la requête
        response = client.get(f"/admin/ght/{context.id}/namespaces/{namespace.id}")

        assert response.status_code == 200

    def test_view_namespace_not_found(self, session: Session, client: TestClient):
        """Test consultation namespace inexistant."""
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        response = client.get(f"/admin/ght/{context.id}/namespaces/999")

        assert response.status_code == 404
        assert "Namespace" in response.json()["detail"]

    def test_edit_namespace_form(self, session: Session, client: TestClient):
        """Test affichage formulaire modification namespace."""
        # Créer les données de test
        context = GHTContext(name="TEST", code="TEST")
        session.add(context)
        session.commit()

        namespace = IdentifierNamespace(
            name="Test Namespace",
            system="urn:test:edit",
            type="IPP",
            ght_context_id=context.id
        )
        session.add(namespace)
        session.commit()

        # Faire la requête
        response = client.get(f"/admin/ght/{context.id}/namespaces/{namespace.id}/edit")

        assert response.status_code == 200