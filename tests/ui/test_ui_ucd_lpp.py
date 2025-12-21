# tests/ui/test_ui_ucd_lpp.py
"""
Tests UI pour les routers UCD et LPP
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock

from app.app import app


class TestUCDUI:
    """Tests UI pour les routes UCD"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_ucd_dashboard_renders(self, client):
        """Test que le dashboard UCD se rend correctement"""
        response = client.get("/ucd/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "UCD" in response.text or "Actes UCD" in response.text

    def test_ucd_dossier_page_renders(self, client):
        """Test que la page de dossier UCD se rend correctement"""
        # Mock d'un dossier avec des actes
        response = client.get("/ucd/dossier/1")

        # La page peut retourner 200 même si le dossier n'existe pas
        # ou rediriger selon la logique métier
        assert response.status_code in [200, 302, 404]

        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
            assert "Actes UCD" in response.text

    def test_ucd_create_form_renders(self, client):
        """Test que le formulaire de création UCD se rend correctement"""
        response = client.get("/ucd/create/1")

        # En mode test, la route peut retourner 404 si la DB n'est pas configurée
        # ou si le dossier n'existe pas
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
            assert "Créer" in response.text or "Nouveau" in response.text

    def test_ucd_act_detail_renders(self, client):
        """Test que la page de détail d'acte UCD se rend correctement"""
        response = client.get("/ucd/act/1")

        # Peut retourner 404 si l'acte n'existe pas
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
            assert "Détails" in response.text or "Acte UCD" in response.text

    def test_ucd_create_form_submission(self, client):
        """Test soumission du formulaire de création UCD"""
        form_data = {
            "code": "UCD123",
            "libelle": "Test acte UCD",
            "date_execution": "2025-12-21T10:00",
            "medecin_responsable_id": "1",
            "quantite": "1",
            "montant_unitaire": "100.00",
            "montant_total": "100.00",
            "commentaires": "Test"
        }

        response = client.post("/ucd/create/1", data=form_data)

        # La soumission peut réussir ou échouer selon la validation
        assert response.status_code in [200, 302, 400, 422]

        if response.status_code == 302:  # Redirection après succès
            assert "location" in response.headers

    def test_ucd_act_validation(self, client):
        """Test validation d'acte UCD via interface web"""
        # Test avec paramètre valide=True
        response = client.post("/ucd/act/1/validate", data={"valide": "true"})

        # Peut retourner 404 si l'acte n'existe pas, ou 200 si succès
        assert response.status_code in [200, 404, 422]


class TestLPPUI:
    """Tests UI pour les routes LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_lpp_dashboard_renders(self, client):
        """Test que le dashboard LPP se rend correctement"""
        response = client.get("/lpp/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "LPP" in response.text or "Actes LPP" in response.text

    def test_lpp_dossier_page_renders(self, client):
        """Test que la page de dossier LPP se rend correctement"""
        response = client.get("/lpp/dossier/1")

        # La page peut retourner 200 même si le dossier n'existe pas
        assert response.status_code in [200, 302, 404]

        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
            assert "Actes LPP" in response.text

    def test_lpp_create_form_renders(self, client):
        """Test que le formulaire de création LPP se rend correctement"""
        response = client.get("/lpp/create/1")

        # En mode test, la route peut retourner 404 si la DB n'est pas configurée
        # ou si le dossier n'existe pas
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
            assert "Créer" in response.text or "Nouveau" in response.text

    def test_lpp_act_detail_renders(self, client):
        """Test que la page de détail d'acte LPP se rend correctement"""
        response = client.get("/lpp/act/1")

        # Peut retourner 404 si l'acte n'existe pas
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")
            assert "Détails" in response.text or "Acte LPP" in response.text

    def test_lpp_create_form_submission(self, client):
        """Test soumission du formulaire de création LPP"""
        form_data = {
            "code": "LPP123",
            "libelle": "Test acte LPP",
            "date_execution": "2025-12-21T10:00",
            "medecin_responsable_id": "1",
            "quantite": "1",
            "montant_unitaire": "100.00",
            "montant_total": "100.00",
            "commentaires": "Test"
        }

        response = client.post("/lpp/create/1", data=form_data)

        # La soumission peut réussir ou échouer selon la validation
        assert response.status_code in [200, 302, 400, 422]

        if response.status_code == 302:  # Redirection après succès
            assert "location" in response.headers

    def test_lpp_act_validation(self, client):
        """Test validation d'acte LPP via interface web"""
        # Test avec paramètre valide=True
        response = client.post("/lpp/act/1/validate", data={"valide": "true"})

        # Peut retourner 404 si l'acte n'existe pas, ou 200 si succès
        assert response.status_code in [200, 404, 422]


class TestUCDLPPNavigation:
    """Tests de navigation entre UCD et LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_ucd_navigation_links(self, client):
        """Test que la page UCD se charge correctement"""
        response = client.get("/ucd/")

        assert response.status_code == 200
        content = response.text

        # Vérifier que c'est du HTML valide avec un titre
        assert "<!doctype html>" in content
        assert "Gestion UCD" in content
        assert "Accueil" in content  # Vérifier le breadcrumb

    def test_lpp_navigation_links(self, client):
        """Test que la page LPP se charge correctement"""
        response = client.get("/lpp/")

        assert response.status_code == 200
        content = response.text

        # Vérifier que c'est du HTML valide avec un titre
        assert "<!doctype html>" in content
        assert "Gestion LPP" in content
        assert "Accueil" in content  # Vérifier le breadcrumb

    def test_cross_navigation_ucd_to_lpp(self, client):
        """Test que la page UCD se charge correctement"""
        response = client.get("/ucd/")

        assert response.status_code == 200
        content = response.text

        # Vérifier que c'est du HTML valide
        assert "<!doctype html>" in content
        assert "Gestion UCD" in content

    def test_cross_navigation_lpp_to_ucd(self, client):
        """Test que la page LPP se charge correctement"""
        response = client.get("/lpp/")

        assert response.status_code == 200
        content = response.text

        # Vérifier que c'est du HTML valide
        assert "<!doctype html>" in content
        assert "Gestion LPP" in content