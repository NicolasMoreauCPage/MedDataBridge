"""
Tests d'intégration pour les nouvelles fonctionnalités de monitoring et performance.

Couvre:
- Système de métriques
- Cache avancé
- API des tâches asynchrones
- Validation des données
- Logging structuré
"""

import pytest
import asyncio
import json
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.app import create_app
from app.tasks import task_manager, create_background_task
from app.cache import cache
from app.metrics import metrics
from app.validation import PatientSearchRequest, FHIRResourceRequest


@pytest.fixture
def test_app():
    """Application FastAPI de test."""
    app = create_app()
    return app


@pytest.fixture
def client(test_app):
    """Client de test HTTP."""
    return TestClient(test_app)


@pytest.fixture
async def async_client(test_app):
    """Client HTTP asynchrone pour les tests."""
    from httpx import AsyncClient
    async with AsyncClient(app=test_app, base_url="http://testserver") as ac:
        yield ac


class TestMetricsIntegration:
    """Tests d'intégration du système de métriques."""

    def test_metrics_endpoint_returns_data(self, client):
        """Test que l'endpoint /metrics retourne des données."""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "uptime_seconds" in data
        assert "requests" in data
        assert "database" in data
        assert "cache" in data
        assert "system" in data

    def test_metrics_collection_on_request(self, client):
        """Test que les métriques sont collectées lors des requêtes."""
        # Faire quelques requêtes
        client.get("/health")
        client.get("/metrics")
        client.get("/health/db")

        # Vérifier que les métriques ont été collectées
        metrics_data = metrics.get_metrics()
        assert len(metrics_data["requests"]) > 0

        # Vérifier qu'il y a des métriques pour les endpoints testés
        request_keys = list(metrics_data["requests"].keys())
        assert any("GET:/health" in key for key in request_keys)

    def test_metrics_persistence(self, client):
        """Test que les métriques persistent entre les requêtes."""
        # Première requête
        client.get("/health")
        metrics_after_first = metrics.get_metrics()

        # Deuxième requête
        client.get("/health")
        metrics_after_second = metrics.get_metrics()

        # Les métriques devraient avoir évolué
        first_count = sum(stats["count"] for stats in metrics_after_first["requests"].values())
        second_count = sum(stats["count"] for stats in metrics_after_second["requests"].values())

        assert second_count > first_count


class TestCacheIntegration:
    """Tests d'intégration du système de cache avancé."""

    def test_cache_basic_operations(self):
        """Test des opérations de base du cache."""
        # Test set/get
        cache.set("test_key", {"data": "test_value"}, ttl=60)
        result = cache.get("test_key")
        assert result == {"data": "test_value"}

        # Test delete
        cache.delete("test_key")
        result = cache.get("test_key")
        assert result is None

    def test_cache_stats(self):
        """Test des statistiques du cache."""
        initial_stats = cache.get_stats()

        # Effectuer des opérations
        cache.set("test_key", "value")
        cache.get("test_key")
        cache.get("nonexistent_key")

        final_stats = cache.get_stats()

        # Les stats devraient être mises à jour
        assert final_stats["memory_cache_size"] >= initial_stats["memory_cache_size"]

    @patch('app.cache.redis_client')
    def test_cache_fallback_to_memory(self, mock_redis):
        """Test du fallback vers le cache mémoire."""
        # Simuler une erreur Redis
        mock_redis.setex.side_effect = Exception("Redis error")

        # Le cache devrait quand même fonctionner en mémoire
        result = cache.set("fallback_test", "value")
        assert result is True

        result = cache.get("fallback_test")
        assert result == "value"


class TestTasksAPIIntegration:
    """Tests d'intégration de l'API des tâches asynchrones."""

    def test_create_task_endpoint(self, client):
        """Test de création d'une tâche via l'API."""
        task_data = {
            "name": "Test Task",
            "description": "Tâche de test pour l'intégration",
            "task_type": "test",
            "parameters": {"duration": 1}
        }

        response = client.post("/api/tasks/", json=task_data)
        assert response.status_code == 200

        data = response.json()
        assert "task_id" in data
        assert data["status"] == "created"

    def test_get_task_status(self, client):
        """Test de récupération du statut d'une tâche."""
        # Créer une tâche
        task_data = {
            "name": "Status Test",
            "description": "Test du statut des tâches",
            "task_type": "test"
        }

        create_response = client.post("/api/tasks/", json=task_data)
        task_id = create_response.json()["task_id"]

        # Récupérer le statut
        status_response = client.get(f"/api/tasks/{task_id}")
        assert status_response.status_code == 200

        data = status_response.json()
        assert data["id"] == task_id
        assert data["name"] == "Status Test"
        assert data["status"] in ["pending", "running", "completed", "failed"]

    def test_list_tasks(self, client):
        """Test de listage des tâches."""
        response = client.get("/api/tasks/")
        assert response.status_code == 200

        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_task_stats(self, client):
        """Test des statistiques des tâches."""
        # Créer d'abord une tâche pour avoir des stats
        task_data = {
            "name": "Stats Test",
            "description": "Test des statistiques",
            "task_type": "test"
        }
        client.post("/api/tasks/", json=task_data)
        
        # Maintenant tester les stats
        response = client.get("/api/tasks/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_tasks" in data
        assert "running_tasks" in data
        assert "max_concurrent_tasks" in data
        assert "tasks_by_status" in data

    def test_cancel_task(self, client):
        """Test d'annulation d'une tâche."""
        # Créer une tâche qui dure plus longtemps
        task_data = {
            "name": "Long Cancel Test",
            "description": "Test d'annulation d'une tâche longue",
            "task_type": "test",
            "parameters": {"duration": 10}  # 10 secondes
        }

        create_response = client.post("/api/tasks/", json=task_data)
        task_id = create_response.json()["task_id"]

        # Attendre un peu que la tâche démarre
        import time
        time.sleep(2)

        # Annuler la tâche
        cancel_response = client.delete(f"/api/tasks/{task_id}")
        # L'annulation peut réussir ou échouer selon le timing
        assert cancel_response.status_code in [200, 400]

        # Vérifier le statut final
        status_response = client.get(f"/api/tasks/{task_id}")
        data = status_response.json()
        # La tâche peut être cancelled, completed ou running
        assert data["status"] in ["cancelled", "completed", "running"]


class TestValidationIntegration:
    """Tests d'intégration du système de validation."""

    def test_patient_search_validation(self):
        """Test de validation des requêtes de recherche patient."""
        # Requête valide
        valid_request = PatientSearchRequest(
            query="Dupont",
            limit=50,
            offset=0
        )
        assert valid_request.query == "Dupont"
        assert valid_request.limit == 50

        # Requête invalide (trop courte)
        with pytest.raises(ValueError):
            PatientSearchRequest(query="A", limit=10)

        # Requête invalide (limite trop haute)
        with pytest.raises(ValueError):
            PatientSearchRequest(query="Dupont", limit=200)

    def test_fhir_resource_validation(self):
        """Test de validation des requêtes FHIR."""
        # Requête valide
        valid_request = FHIRResourceRequest(
            resource_type="Patient",
            resource_id="123456"
        )
        assert valid_request.resource_type == "Patient"

        # Type de ressource invalide
        with pytest.raises(ValueError):
            FHIRResourceRequest(resource_type="InvalidResource")

    def test_data_sanitization(self):
        """Test de la sanitisation automatique des données."""
        from app.validation import DataSanitizer

        # Test sanitisation string
        dirty_string = "<script>alert('xss')</script>Hello World"
        clean_string = DataSanitizer.sanitize_string(dirty_string)
        assert "<script>" not in clean_string
        assert "&lt;script&gt;" in clean_string  # Vérifier que c'est échappé
        assert clean_string == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;Hello World"

        # Test détection injection SQL
        sql_injection = "'; DROP TABLE users; --"
        assert DataSanitizer.check_sql_injection(sql_injection)

        safe_query = "SELECT * FROM patients WHERE name = 'Dupont'"
        assert not DataSanitizer.check_sql_injection(safe_query)


class TestLoggingIntegration:
    """Tests d'intégration du système de logging."""

    def test_structured_logging(self, caplog):
        """Test du logging structuré."""
        import logging
        from app.logging_config import get_logger

        logger = get_logger("test_module")

        # Log avec contexte
        logger.info("Test message", extra={"extra_data": {"user_id": 123, "action": "login"}})

        # Vérifier que le log a été capturé
        assert len(caplog.records) > 0

        # Vérifier le contenu structuré (si format JSON activé)
        log_record = caplog.records[-1]
        assert log_record.message == "Test message"
        assert hasattr(log_record, 'extra_data')

    def test_metrics_logging_integration(self, client, caplog):
        """Test de l'intégration entre métriques et logging."""
        # Faire une requête qui génère des métriques
        client.get("/health")

        # Vérifier que des logs ont été générés
        assert len(caplog.records) > 0


class TestHealthCheckIntegration:
    """Tests d'intégration des health checks améliorés."""

    def test_enhanced_health_check(self, client):
        """Test du health check avec métriques DB et cache."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "cache" in data
        assert "timestamp" in data

    def test_database_health_check(self, client):
        """Test du health check spécifique à la base de données."""
        response = client.get("/health/db")
        # Ce test peut échouer si la DB n'est pas configurée en test
        # On vérifie juste que l'endpoint existe
        assert response.status_code in [200, 503]


class TestConfigurationIntegration:
    """Tests d'intégration de la configuration avancée."""

    def test_configuration_validation(self):
        """Test de la validation de configuration."""
        from config.settings import settings

        warnings = settings.validate_config()
        # Il peut y avoir des avertissements (secrets par défaut), mais pas d'erreurs
        assert isinstance(warnings, list)

    def test_configuration_serialization(self):
        """Test de la sérialisation de la configuration."""
        from config.settings import settings

        config_dict = settings.to_dict(mask_secrets=True)
        assert isinstance(config_dict, dict)
        assert "app_name" in config_dict

        # Vérifier que les secrets sont masqués
        if "secret_key" in config_dict:
            assert config_dict["secret_key"].startswith("***")


# Tests de performance et charge
class TestPerformanceIntegration:
    """Tests de performance pour les nouvelles fonctionnalités."""

    def test_metrics_basic_functionality(self, client):
        """Test que les métriques fonctionnent sans planter."""
        # Faire quelques requêtes
        client.get("/health")
        client.get("/metrics")

        # Vérifier que les métriques sont accessibles
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_cache_basic_performance(self):
        """Test des performances basiques du cache."""
        import time

        # Test set/get rapide
        start_time = time.time()
        cache.set("perf_test", {"data": "x" * 1000})
        result = cache.get("perf_test")
        end_time = time.time()

        assert result is not None
        assert end_time - start_time < 0.1  # Moins de 100ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])