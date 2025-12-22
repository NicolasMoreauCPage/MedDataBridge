# tests/performance/test_ucd_lpp_performance.py
"""
Tests de performance pour UCD et LPP
Tests de charge, temps de réponse et utilisation mémoire
"""

import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import asyncio
from concurrent.futures import ThreadPoolExecutor
import psutil
import os

from app.app import app


class TestUCDPerformance:
    """Tests de performance pour UCD"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_ucd_api_response_time(self, client):
        """Test temps de réponse des API UCD"""
        start_time = time.time()
        response = client.get("/api/ucd/dossier/1")
        end_time = time.time()

        response_time = end_time - start_time

        # Temps de réponse devrait être inférieur à 500ms
        assert response_time < 0.5, f"Temps de réponse trop lent: {response_time:.3f}s"
        assert response.status_code in [200, 404, 422]

    def test_ucd_ui_response_time(self, client):
        """Test temps de réponse des routes UI UCD"""
        routes = ["/ucd/", "/ucd/dossier/1", "/ucd/create/1"]

        for route in routes:
            start_time = time.time()
            response = client.get(route)
            end_time = time.time()

            response_time = end_time - start_time

            # Temps de réponse devrait être inférieur à 1s pour les routes UI
            assert response_time < 1.0, f"Route {route} trop lente: {response_time:.3f}s"
            assert response.status_code in [200, 302, 404]

    @pytest.mark.asyncio
    async def test_ucd_concurrent_requests(self, client):
        """Test requêtes concurrentes UCD"""
        async def make_request():
            return client.get("/api/ucd/dossier/1")

        # Lancer 10 requêtes concurrentes
        tasks = [make_request() for _ in range(10)]
        start_time = time.time()

        responses = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Toutes les requêtes devraient réussir
        for response in responses:
            assert response.status_code in [200, 404, 422]

        # Le temps total devrait être raisonnable (pas plus de 2s pour 10 requêtes)
        assert total_time < 2.0, f"Temps total trop élevé: {total_time:.3f}s"

    def test_ucd_memory_usage(self, client):
        """Test utilisation mémoire pour les opérations UCD"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Effectuer plusieurs opérations
        for i in range(50):
            response = client.get("/api/ucd/dossier/1")
            assert response.status_code in [200, 404, 422]

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # L'augmentation de mémoire devrait être limitée (< 50MB)
        assert memory_increase < 50, f"Augmentation mémoire excessive: {memory_increase:.2f}MB"


class TestLPPPerformance:
    """Tests de performance pour LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_lpp_api_response_time(self, client):
        """Test temps de réponse des API LPP"""
        start_time = time.time()
        response = client.get("/api/lpp/dossier/1")
        end_time = time.time()

        response_time = end_time - start_time

        # Temps de réponse devrait être inférieur à 500ms
        assert response_time < 0.5, f"Temps de réponse trop lent: {response_time:.3f}s"
        assert response.status_code in [200, 404, 422]

    def test_lpp_ui_response_time(self, client):
        """Test temps de réponse des routes UI LPP"""
        routes = ["/lpp/", "/lpp/dossier/1", "/lpp/create/1"]

        for route in routes:
            start_time = time.time()
            response = client.get(route)
            end_time = time.time()

            response_time = end_time - start_time

            # Temps de réponse devrait être inférieur à 1s pour les routes UI
            assert response_time < 1.0, f"Route {route} trop lente: {response_time:.3f}s"
            assert response.status_code in [200, 302, 404]

    @pytest.mark.asyncio
    async def test_lpp_concurrent_requests(self, client):
        """Test requêtes concurrentes LPP"""
        async def make_request():
            return client.get("/api/lpp/dossier/1")

        # Lancer 10 requêtes concurrentes
        tasks = [make_request() for _ in range(10)]
        start_time = time.time()

        responses = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Toutes les requêtes devraient réussir
        for response in responses:
            assert response.status_code in [200, 404, 422]

        # Le temps total devrait être raisonnable (pas plus de 2s pour 10 requêtes)
        assert total_time < 2.0, f"Temps total trop élevé: {total_time:.3f}s"

    def test_lpp_memory_usage(self, client):
        """Test utilisation mémoire pour les opérations LPP"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Effectuer plusieurs opérations
        for i in range(50):
            response = client.get("/api/lpp/dossier/1")
            assert response.status_code in [200, 404, 422]

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # L'augmentation de mémoire devrait être limitée (< 50MB)
        assert memory_increase < 50, f"Augmentation mémoire excessive: {memory_increase:.2f}MB"


class TestUCDLPPPerformanceComparison:
    """Tests comparant les performances UCD vs LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_ucd_lpp_response_time_comparison(self, client):
        """Comparaison des temps de réponse UCD vs LPP"""
        routes_ucd = ["/api/ucd/dossier/1", "/ucd/", "/ucd/create/1"]
        routes_lpp = ["/api/lpp/dossier/1", "/lpp/", "/lpp/create/1"]

        times_ucd = []
        times_lpp = []

        # Mesurer les temps UCD
        for route in routes_ucd:
            start = time.time()
            response = client.get(route)
            end = time.time()
            times_ucd.append(end - start)
            assert response.status_code in [200, 302, 404, 422]

        # Mesurer les temps LPP
        for route in routes_lpp:
            start = time.time()
            response = client.get(route)
            end = time.time()
            times_lpp.append(end - start)
            assert response.status_code in [200, 302, 404, 422]

        # Les performances devraient être similaires (différence < 20%)
        avg_ucd = sum(times_ucd) / len(times_ucd)
        avg_lpp = sum(times_lpp) / len(times_lpp)

        ratio = max(avg_ucd, avg_lpp) / min(avg_ucd, avg_lpp)
        assert ratio < 1.2, f"Performances trop différentes: UCD={avg_ucd:.3f}s, LPP={avg_lpp:.3f}s"

    def test_ucd_lpp_concurrent_performance(self, client):
        """Test performances concurrentes comparées"""
        def test_concurrent(route, num_requests=20):
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(client.get, route) for _ in range(num_requests)]
                responses = [f.result() for f in futures]
            end_time = time.time()

            # Vérifier que toutes les requêtes ont réussi
            for response in responses:
                assert response.status_code in [200, 302, 404, 422]

            return end_time - start_time

        time_ucd = test_concurrent("/api/ucd/dossier/1")
        time_lpp = test_concurrent("/api/lpp/dossier/1")

        # Les performances concurrentes devraient être similaires
        ratio = max(time_ucd, time_lpp) / min(time_ucd, time_lpp)
        assert ratio < 1.5, f"Performances concurrentes différentes: UCD={time_ucd:.3f}s, LPP={time_lpp:.3f}s"

    def test_ucd_lpp_memory_efficiency(self, client):
        """Test efficacité mémoire comparée"""
        process = psutil.Process(os.getpid())

        # Test UCD
        initial_memory = process.memory_info().rss / 1024 / 1024
        for i in range(100):
            client.get("/api/ucd/dossier/1")
        ucd_memory = process.memory_info().rss / 1024 / 1024 - initial_memory

        # Test LPP
        initial_memory = process.memory_info().rss / 1024 / 1024
        for i in range(100):
            client.get("/api/lpp/dossier/1")
        lpp_memory = process.memory_info().rss / 1024 / 1024 - initial_memory

        # L'utilisation mémoire devrait être similaire
        ratio = max(ucd_memory, lpp_memory) / max(min(ucd_memory, lpp_memory), 0.1)  # éviter division par zéro
        assert ratio < 2.0, f"Utilisation mémoire différente: UCD={ucd_memory:.2f}MB, LPP={lpp_memory:.2f}MB"


class TestUCDLPPLoadTesting:
    """Tests de charge pour UCD et LPP"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    @pytest.mark.slow
    def test_ucd_high_load(self, client):
        """Test charge élevée pour UCD"""
        num_requests = 200

        start_time = time.time()
        responses = []

        for i in range(num_requests):
            response = client.get("/api/ucd/dossier/1")
            responses.append(response)
            # Petit délai pour éviter de surcharger
            time.sleep(0.01)

        end_time = time.time()
        total_time = end_time - start_time

        # Vérifier que toutes les requêtes ont réussi
        success_count = sum(1 for r in responses if r.status_code in [200, 404, 422])
        success_rate = success_count / num_requests

        assert success_rate > 0.95, f"Taux de succès trop faible: {success_rate:.2%}"
        assert total_time < 30, f"Test de charge trop lent: {total_time:.2f}s pour {num_requests} requêtes"

    @pytest.mark.slow
    def test_lpp_high_load(self, client):
        """Test charge élevée pour LPP"""
        num_requests = 200

        start_time = time.time()
        responses = []

        for i in range(num_requests):
            response = client.get("/api/lpp/dossier/1")
            responses.append(response)
            # Petit délai pour éviter de surcharger
            time.sleep(0.01)

        end_time = time.time()
        total_time = end_time - start_time

        # Vérifier que toutes les requêtes ont réussi
        success_count = sum(1 for r in responses if r.status_code in [200, 404, 422])
        success_rate = success_count / num_requests

        assert success_rate > 0.95, f"Taux de succès trop faible: {success_rate:.2%}"
        assert total_time < 30, f"Test de charge trop lent: {total_time:.2f}s pour {num_requests} requêtes"

    @pytest.mark.slow
    def test_ucd_bulk_acts_creation(self, session: Session, sample_ght):
        """Test création en masse d'actes UCD (1000+ actes)"""
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        from app.services.ucd_service import UCDService
        from app.schemas.ucd import UCDActCreate
        from datetime import datetime

        # Créer un patient et dossier de test
        patient_data = PatientCreateSchema(
            family="BulkTest",
            given="Patient",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            uf_responsabilite="UF001",
            dossier_type="hospitalise",
            admit_time=datetime.now()
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Mesurer la création de 1000 actes UCD
        ucd_service = UCDService(session)
        start_time = time.time()
        created_acts = []

        for i in range(1000):
            act_data = UCDActCreate(
                dossier_id=dossier.id,
                code_cip="3400935001325",
                designation=f"Médicament Test {i}",
                quantite=1,
                prix_unitaire=10.0 + i * 0.01,  # Prix légèrement différent
                montant_total=10.0 + i * 0.01,
                execute_date=datetime.now(),
                prestataire_id="PREST001",
                commentaire=f"Test acte {i}"
            )
            act = await ucd_service.create_act(act_data)
            created_acts.append(act)

        end_time = time.time()
        creation_time = end_time - start_time

        # Vérifications
        assert len(created_acts) == 1000
        assert creation_time < 60, f"Création de 1000 actes trop lente: {creation_time:.2f}s"
        assert all(act.id is not None for act in created_acts)

        # Test récupération des actes créés
        start_time = time.time()
        retrieved_acts = await ucd_service.get_acts_by_dossier(dossier.id)
        end_time = time.time()
        retrieval_time = end_time - start_time

        assert len(retrieved_acts) == 1000
        assert retrieval_time < 5, f"Récupération de 1000 actes trop lente: {retrieval_time:.2f}s"