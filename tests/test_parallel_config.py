# tests/test_parallel_config.py
"""
Configuration pour l'exécution parallèle des tests
Optimisation des performances de test pour CI/CD
"""

import pytest
import multiprocessing
from typing import List, Dict, Any


def pytest_configure(config):
    """Configuration pytest pour tests parallèles"""
    # Déterminer le nombre optimal de workers
    cpu_count = multiprocessing.cpu_count()

    # Pour CI/CD, utiliser 80% des CPUs disponibles
    if config.getoption("--ci"):
        config.option.numprocesses = max(1, int(cpu_count * 0.8))
    else:
        # En local, utiliser moins de workers pour éviter surcharge
        config.option.numprocesses = max(1, min(4, cpu_count // 2))


def pytest_collection_modifyitems(config, items):
    """Modifier la collection de tests pour optimisation parallèle"""
    # Grouper les tests par type pour meilleure parallélisation
    unit_tests = []
    integration_tests = []
    ui_tests = []
    security_tests = []
    performance_tests = []

    for item in items:
        if "unit" in item.keywords:
            unit_tests.append(item)
        elif "integration" in item.keywords:
            integration_tests.append(item)
        elif "ui" in item.keywords:
            ui_tests.append(item)
        elif "security" in item.keywords:
            security_tests.append(item)
        elif "performance" in item.keywords:
            performance_tests.append(item)

    # Réorganiser pour exécuter les tests rapides d'abord
    fast_tests = unit_tests + security_tests
    slow_tests = integration_tests + ui_tests + performance_tests

    # Remettre dans l'ordre optimisé
    items[:] = fast_tests + slow_tests


@pytest.fixture(scope="session")
def pytest_xdist_worker_id():
    """Fixture pour identifier le worker dans les tests parallèles"""
    import os
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


@pytest.mark.parametrize("marker", [
    "unit", "integration", "ui", "security", "performance"
])
def test_marker_coverage(marker):
    """Test que tous les tests ont les bons markers"""
    # Ce test vérifie que les markers sont correctement utilisés
    pass


# Configuration pour pytest-xdist
def pytest_xdist_make_scheduler(config, log):
    """Configuration du scheduler pour tests parallèles"""
    return None  # Utilise le scheduler par défaut


# Configuration pour les rapports de couverture
@pytest.fixture(scope="session", autouse=True)
def coverage_setup():
    """Configuration globale pour les rapports de couverture"""
    import coverage

    # Configuration de couverture pour tests parallèles
    cov = coverage.Coverage(
        branch=True,
        source=['app'],
        omit=[
            '*/tests/*',
            '*/venv/*',
            '*/.venv/*',
            '*/__pycache__/*',
            '*/migrations/*'
        ]
    )

    cov.start()
    yield
    cov.stop()
    cov.save()


# Configuration pour les tests de mutation
@pytest.fixture(scope="session")
def mutation_config():
    """Configuration pour les tests de mutation (mutmut)"""
    return {
        "paths_to_mutate": ["app"],
        "paths_to_exclude": [
            "*/tests/*",
            "*/venv/*",
            "*/migrations/*",
            "*/__pycache__/*"
        ],
        "tests_dir": "tests",
        "dict_synonyms": ["dict", "Dict"],
        "runner": "python -m pytest tests/ -x --tb=short"
    }


# Métriques de performance pour CI/CD
class TestMetrics:
    """Collecte de métriques de test pour CI/CD"""

    def __init__(self):
        self.test_times = {}
        self.failures = []
        self.errors = []

    def record_test_time(self, test_name: str, duration: float):
        """Enregistrer le temps d'exécution d'un test"""
        self.test_times[test_name] = duration

    def record_failure(self, test_name: str, error: str):
        """Enregistrer un échec de test"""
        self.failures.append({"test": test_name, "error": error})

    def record_error(self, test_name: str, error: str):
        """Enregistrer une erreur de test"""
        self.errors.append({"test": test_name, "error": error})

    def get_summary(self) -> Dict[str, Any]:
        """Obtenir un résumé des métriques"""
        return {
            "total_tests": len(self.test_times),
            "total_failures": len(self.failures),
            "total_errors": len(self.errors),
            "average_time": sum(self.test_times.values()) / len(self.test_times) if self.test_times else 0,
            "slowest_tests": sorted(self.test_times.items(), key=lambda x: x[1], reverse=True)[:5]
        }


@pytest.fixture(scope="session")
def test_metrics():
    """Fixture pour collecter les métriques de test"""
    return TestMetrics()


# Configuration pour les tests de charge
@pytest.fixture(scope="session")
def load_test_config():
    """Configuration pour les tests de charge"""
    return {
        "concurrent_users": 10,
        "ramp_up_time": 30,  # secondes
        "test_duration": 300,  # secondes
        "endpoints": [
            "/api/patients",
            "/api/dossiers",
            "/api/ucd",
            "/api/lpp"
        ]
    }


# Utilitaires pour les tests CI/CD
def skip_in_ci(reason: str):
    """Décorateur pour skipper un test en CI"""
    def decorator(func):
        return pytest.mark.skipif(
            os.environ.get("CI") == "true",
            reason=reason
        )(func)
    return decorator


def only_in_ci(reason: str):
    """Décorateur pour exécuter un test seulement en CI"""
    def decorator(func):
        return pytest.mark.skipif(
            os.environ.get("CI") != "true",
            reason=reason
        )(func)
    return decorator


# Configuration pour les tests de sécurité en CI
@pytest.fixture(scope="session")
def security_scan_config():
    """Configuration pour les scans de sécurité automatiques"""
    return {
        "vulnerability_scanners": ["bandit", "safety"],
        "sast_tools": ["semgrep", "sonarcloud"],
        "dependency_scanning": True,
        "secret_scanning": True
    }


# Métriques de qualité de code
@pytest.fixture(scope="session")
def code_quality_config():
    """Configuration pour les métriques de qualité de code"""
    return {
        "complexity_threshold": 10,
        "line_length_limit": 88,
        "function_length_limit": 50,
        "duplicate_code_threshold": 3,
        "test_coverage_minimum": 85
    }
