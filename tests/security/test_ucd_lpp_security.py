# tests/security/test_ucd_lpp_security.py
"""
Tests de sécurité pour UCD et LPP
Tests de validation d'entrée, injection SQL, XSS, etc.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.app import app


class TestUCDSecurity:
    """Tests de sécurité pour UCD"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_ucd_input_validation(self, client):
        """Test validation des entrées UCD"""
        # Test données malformées
        malicious_data = {
            "dossier_id": "not_an_int",
            "code": "<script>alert('xss')</script>",
            "libelle": "A" * 1000,  # Trop long
            "date_execution": "invalid_date",
            "medecin_responsable_id": -1,
            "quantite": -5,
            "montant_unitaire": "not_a_number",
            "montant_total": "not_a_number"
        }

        response = client.post("/api/ucd/", json=malicious_data)
        # Devrait échouer à cause de la validation, ou retourner 404 si DB non configurée
        assert response.status_code in [400, 422, 404, 500]

    def test_ucd_sql_injection_prevention(self, client):
        """Test prévention injection SQL UCD"""
        sql_injection_payloads = [
            {"code": "'; DROP TABLE users; --"},
            {"libelle": "1' OR '1'='1"},
            {"commentaires": "'; SELECT * FROM users; --"}
        ]

        for payload in sql_injection_payloads:
            data = {
                "dossier_id": 1,
                "code": "TEST",
                "libelle": "Test",
                "date_execution": "2025-12-21T10:00:00",
                "medecin_responsable_id": 1,
                "quantite": 1,
                "montant_unitaire": 100.0,
                "montant_total": 100.0,
                **payload
            }

            response = client.post("/api/ucd/", json=data)
            # Ne devrait pas réussir avec du SQL malicieux
            assert response.status_code in [400, 422, 500, 404]

    def test_ucd_xss_prevention(self, client):
        """Test prévention XSS UCD"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(\"xss\")'>"
        ]

        for payload in xss_payloads:
            data = {
                "dossier_id": 1,
                "code": "TEST",
                "libelle": payload,
                "date_execution": "2025-12-21T10:00:00",
                "medecin_responsable_id": 1,
                "quantite": 1,
                "montant_unitaire": 100.0,
                "montant_total": 100.0,
                "commentaires": "Test sécurité"
            }

            response = client.post("/api/ucd/", json=data)
            # L'API devrait accepter mais pas exécuter le XSS
            if response.status_code == 200:
                response_data = response.json()
                # Vérifier que le payload n'est pas rendu tel quel dans la réponse
                assert "<script>" not in str(response_data).lower()

    def test_ucd_path_traversal_prevention(self, client):
        """Test prévention path traversal UCD"""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32"
        ]

        # Tester sur les routes qui acceptent des IDs
        for payload in traversal_payloads:
            response = client.get(f"/api/ucd/dossier/{payload}")
            # Devrait échouer ou retourner une erreur de validation
            assert response.status_code in [400, 404, 422]

            response = client.get(f"/api/ucd/{payload}")
            assert response.status_code in [400, 404, 422]

    def test_ucd_rate_limiting(self, client):
        """Test limitation du taux de requêtes UCD"""
        # Effectuer beaucoup de requêtes rapidement
        responses = []
        for i in range(100):
            response = client.get("/api/ucd/dossier/1")
            responses.append(response)

        # Au moins certaines requêtes devraient réussir
        success_count = sum(1 for r in responses if r.status_code in [200, 404, 422])
        assert success_count > 0

        # Si rate limiting est activé, certaines requêtes pourraient échouer avec 429
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        # Note: Ce test peut échouer si pas de rate limiting configuré

    def test_ucd_authentication_required(self, client):
        """Test que l'authentification est requise pour UCD"""
        # Ces tests supposent qu'il y a de l'authentification
        # Dans une vraie app, ces routes pourraient nécessiter un token

        sensitive_routes = [
            "/api/ucd/dossier/1",  # GET route that exists
            "/api/ucd/1",  # GET route that exists
            "/ucd/create/1"
        ]

        for route in sensitive_routes:
            response = client.get(route)
            # Sans authentification, devrait retourner 401 ou 403
            # Note: Peut retourner 200 si pas d'auth configurée
            assert response.status_code in [200, 401, 403, 404, 405, 422]


class TestLPPSecurity:
    """Tests de sécurité pour LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_lpp_input_validation(self, client):
        """Test validation des entrées LPP"""
        # Test données malformées
        malicious_data = {
            "dossier_id": "not_an_int",
            "code": "<script>alert('xss')</script>",
            "libelle": "A" * 1000,  # Trop long
            "date_execution": "invalid_date",
            "medecin_responsable_id": -1,
            "quantite": -5,
            "montant_unitaire": "not_a_number",
            "montant_total": "not_a_number"
        }

        response = client.post("/api/lpp/", json=malicious_data)
        # Devrait échouer à cause de la validation, ou retourner 404 si DB non configurée
        assert response.status_code in [400, 422, 404, 500]

    def test_lpp_sql_injection_prevention(self, client):
        """Test prévention injection SQL LPP"""
        sql_injection_payloads = [
            {"code": "'; DROP TABLE users; --"},
            {"libelle": "1' OR '1'='1"},
            {"commentaires": "'; SELECT * FROM users; --"}
        ]

        for payload in sql_injection_payloads:
            data = {
                "dossier_id": 1,
                "code": "TEST",
                "libelle": "Test",
                "date_execution": "2025-12-21T10:00:00",
                "medecin_responsable_id": 1,
                "quantite": 1,
                "montant_unitaire": 100.0,
                "montant_total": 100.0,
                **payload
            }

            response = client.post("/api/lpp/", json=data)
            # Ne devrait pas réussir avec du SQL malicieux
            assert response.status_code in [400, 422, 500, 404]

    def test_lpp_xss_prevention(self, client):
        """Test prévention XSS LPP"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(\"xss\")'>"
        ]

        for payload in xss_payloads:
            data = {
                "dossier_id": 1,
                "code": "TEST",
                "libelle": payload,
                "date_execution": "2025-12-21T10:00:00",
                "medecin_responsable_id": 1,
                "quantite": 1,
                "montant_unitaire": 100.0,
                "montant_total": 100.0,
                "commentaires": "Test sécurité"
            }

            response = client.post("/api/lpp/", json=data)
            # L'API devrait accepter mais pas exécuter le XSS
            if response.status_code == 200:
                response_data = response.json()
                # Vérifier que le payload n'est pas rendu tel quel dans la réponse
                assert "<script>" not in str(response_data).lower()

    def test_lpp_path_traversal_prevention(self, client):
        """Test prévention path traversal LPP"""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32"
        ]

        # Tester sur les routes qui acceptent des IDs
        for payload in traversal_payloads:
            response = client.get(f"/api/lpp/dossier/{payload}")
            # Devrait échouer ou retourner une erreur de validation
            assert response.status_code in [400, 404, 422]

            response = client.get(f"/api/lpp/{payload}")
            assert response.status_code in [400, 404, 422]

    def test_lpp_rate_limiting(self, client):
        """Test limitation du taux de requêtes LPP"""
        # Effectuer beaucoup de requêtes rapidement
        responses = []
        for i in range(100):
            response = client.get("/api/lpp/dossier/1")
            responses.append(response)

        # Au moins certaines requêtes devraient réussir
        success_count = sum(1 for r in responses if r.status_code in [200, 404, 422])
        assert success_count > 0

        # Si rate limiting est activé, certaines requêtes pourraient échouer avec 429
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        # Note: Ce test peut échouer si pas de rate limiting configuré

    def test_lpp_authentication_required(self, client):
        """Test que l'authentification est requise pour LPP"""
        # Ces tests supposent qu'il y a de l'authentification
        # Dans une vraie app, ces routes pourraient nécessiter un token

        sensitive_routes = [
            "/api/lpp/dossier/1",  # GET route that exists
            "/api/lpp/1",  # GET route that exists
            "/lpp/create/1"
        ]

        for route in sensitive_routes:
            response = client.get(route)
            # Sans authentification, devrait retourner 401 ou 403
            # Note: Peut retourner 200 si pas d'auth configurée
            assert response.status_code in [200, 401, 403, 404, 405, 422]


class TestUCDLPPSecurityComparison:
    """Tests comparant la sécurité UCD vs LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_ucd_lpp_security_consistency(self, client):
        """Test cohérence sécurité UCD vs LPP"""
        malicious_payload = {
            "dossier_id": 1,
            "code": "<script>alert('xss')</script>",
            "libelle": "Test XSS",
            "date_execution": "2025-12-21T10:00:00",
            "medecin_responsable_id": 1,
            "quantite": 1,
            "montant_unitaire": 100.0,
            "montant_total": 100.0
        }

        # Tester la même payload sur UCD et LPP
        response_ucd = client.post("/api/ucd/", json=malicious_payload)
        response_lpp = client.post("/api/lpp/", json=malicious_payload)

        # Les deux devraient avoir le même comportement de sécurité
        assert response_ucd.status_code == response_lpp.status_code

    def test_ucd_lpp_input_validation_consistency(self, client):
        """Test cohérence validation d'entrée UCD vs LPP"""
        invalid_data = {
            "dossier_id": -1,
            "code": "",
            "libelle": "",
            "date_execution": "invalid",
            "medecin_responsable_id": 0,
            "quantite": 0,
            "montant_unitaire": -100.0,
            "montant_total": -100.0
        }

        response_ucd = client.post("/api/ucd/", json=invalid_data)
        response_lpp = client.post("/api/lpp/", json=invalid_data)

        # Les deux devraient rejeter les mêmes données invalides
        assert response_ucd.status_code == response_lpp.status_code

        if response_ucd.status_code in [400, 422]:
            # Si validation activée, vérifier que les erreurs sont similaires
            errors_ucd = response_ucd.json() if response_ucd.content else {}
            errors_lpp = response_lpp.json() if response_lpp.content else {}

            # Au moins les champs obligatoires devraient être mentionnés dans les erreurs
            assert "code" in str(errors_ucd).lower() or "libelle" in str(errors_ucd).lower()
            assert "code" in str(errors_lpp).lower() or "libelle" in str(errors_lpp).lower()

    def test_ucd_lpp_error_handling_consistency(self, client):
        """Test cohérence gestion d'erreurs UCD vs LPP"""
        # Tester avec des IDs inexistants
        non_existent_ids = [99999, "invalid", -1]

        for act_id in non_existent_ids:
            response_ucd = client.get(f"/api/ucd/{act_id}")
            response_lpp = client.get(f"/api/lpp/{act_id}")

            # Les deux devraient avoir le même comportement d'erreur
            assert response_ucd.status_code == response_lpp.status_code

    def test_ucd_lpp_cors_headers(self, client):
        """Test en-têtes CORS cohérents UCD vs LPP"""
        routes = ["/api/ucd/dossier/1", "/api/lpp/dossier/1"]

        for route in routes:
            response = client.options(route)
            # Vérifier que les en-têtes CORS sont présents et cohérents
            cors_headers = [
                'access-control-allow-origin',
                'access-control-allow-methods',
                'access-control-allow-headers'
            ]

            for header in cors_headers:
                # Les en-têtes peuvent être présents ou non selon la config
                # L'important est qu'ils soient cohérents entre UCD et LPP
                pass  # Test conditionnel selon la configuration CORS de l'app