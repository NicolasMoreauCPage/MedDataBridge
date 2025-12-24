"""Tests pour le service de statut des scénarios.

Ce module teste les fonctionnalités de récupération du statut des exécutions
de scénarios, y compris les ACK reçus et les états des scénarios.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from sqlmodel import Session, select

from app.services.scenario_status_service import (
    ScenarioStatus,
    get_last_scenario_status,
    get_scenarios_status_for_ej,
    get_scenarios_with_status
)
from app.models_scenarios import InteropScenario
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.models_endpoints import SystemEndpoint
from app.models_structure import EntiteJuridique


class TestScenarioStatusService:
    """Tests pour le service de statut des scénarios."""

    def test_scenario_status_properties(self):
        """Test propriétés de la classe ScenarioStatus."""
        status = ScenarioStatus(
            scenario_id=1,
            scenario_name="Test Scenario",
            ej_id=1,
            ej_name="Test EJ",
            last_run_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            ack_code="AA",
            status="all_aa",
            success_steps=2,
            total_steps=2
        )

        assert status.is_success is True
        assert status.scenario_id == 1
        assert status.scenario_name == "Test Scenario"
        assert status.ej_id == 1
        assert status.ej_name == "Test EJ"
        assert status.ack_code == "AA"
        assert status.status == "all_aa"

    def test_scenario_status_partial_success(self):
        """Test statut partiellement réussi."""
        status = ScenarioStatus(
            scenario_id=1,
            scenario_name="Test Scenario",
            last_run_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            ack_code="AA",
            status="some_aa",
            success_steps=1,
            total_steps=2
        )

        assert status.is_success is False
        assert status.is_partial is True

    def test_get_last_scenario_status_found(self, session: Session):
        """Test récupération dernier statut scénario - trouvé."""
        # Créer les données de test
        ej = EntiteJuridique(name="Test EJ", finess="123456789")
        endpoint = SystemEndpoint(
            name="Test Endpoint",
            kind="MLLP",
            host="localhost",
            port=2575,
            entite_juridique_id=None  # Sera défini après flush
        )
        scenario = InteropScenario(
            key="test_scenario_1",
            name="Test Scenario",
            description="Test scenario",
            is_active=True
        )

        session.add(ej)
        session.add(scenario)
        session.flush()  # Pour obtenir les IDs générés
        
        assert ej.id is not None, "EJ ID should be generated"
        assert scenario.id is not None, "Scenario ID should be generated"

        # Définir la référence EJ pour l'endpoint
        endpoint.entite_juridique_id = ej.id
        session.add(endpoint)
        session.flush()
        
        assert endpoint.id is not None, "Endpoint ID should be generated"

        # Créer une exécution de scénario
        run = ScenarioExecutionRun(
            scenario_id=scenario.id,
            endpoint_id=endpoint.id,
            started_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc),
            status="completed"
        )

        session.add(run)
        session.flush()

        # Créer des logs d'étapes avec ACK
        step_log = ScenarioExecutionStepLog(
            run_id=run.id,
            step_name="Send Message",
            ack_code="AA",
            ack_message="Message accepted",
            timestamp=datetime(2024, 1, 1, 10, 2, tzinfo=timezone.utc)
        )

        session.add(step_log)
        session.commit()

        # Tester la récupération du statut
        status = get_last_scenario_status(session, scenario.id, ej.id)

        assert status is not None
        assert status.scenario_id == scenario.id
        assert status.scenario_name == "Test Scenario"
        assert status.ej_id == ej.id
        assert status.ej_name == "Test EJ"
        assert status.ack_code == "AA"
        assert status.status == "all_aa"
        assert status.is_success is True

    def test_get_last_scenario_status_not_found(self, session: Session):
        """Test récupération dernier statut scénario - non trouvé."""
        status = get_last_scenario_status(session, 999, 999)

        assert status is not None
        assert status.status == "unknown"
        assert status.scenario_id == 999

    def test_get_scenarios_status_for_ej(self, session: Session):
        """Test récupération statuts scénarios pour une EJ."""
        # Créer les données de test
        ej = EntiteJuridique(name="Test EJ", finess="123456789")
        endpoint = SystemEndpoint(
            name="Test Endpoint",
            kind="MLLP",
            host="localhost",
            port=2575,
            entite_juridique_id=None  # Sera défini après flush
        )

        # Créer plusieurs scénarios
        scenario1 = InteropScenario(
            key="scenario_1",
            name="Scenario 1",
            description="First scenario",
            is_active=True
        )
        scenario2 = InteropScenario(
            key="scenario_2",
            name="Scenario 2",
            description="Second scenario",
            is_active=True
        )

        session.add(ej)
        session.add(scenario1)
        session.add(scenario2)
        session.flush()  # Pour obtenir les IDs générés

        # Définir la référence EJ pour l'endpoint
        endpoint.entite_juridique_id = ej.id
        session.add(endpoint)
        session.flush()

        # Créer des exécutions pour les scénarios
        run1 = ScenarioExecutionRun(
            scenario_id=scenario1.id,
            endpoint_id=endpoint.id,
            started_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc),
            status="completed"
        )
        run2 = ScenarioExecutionRun(
            scenario_id=scenario2.id,
            endpoint_id=endpoint.id,
            started_at=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
            finished_at=datetime(2024, 1, 1, 11, 5, tzinfo=timezone.utc),
            status="completed"
        )

        session.add(run1)
        session.add(run2)
        session.flush()

        # Créer des logs d'étapes
        step_log1 = ScenarioExecutionStepLog(
            run_id=run1.id,
            step_name="Send Message",
            ack_code="AA",
            ack_message="Accepted",
            timestamp=datetime(2024, 1, 1, 10, 2, tzinfo=timezone.utc)
        )
        step_log2 = ScenarioExecutionStepLog(
            run_id=run2.id,
            step_name="Send Message",
            ack_code="AE",
            ack_message="Error",
            timestamp=datetime(2024, 1, 1, 11, 2, tzinfo=timezone.utc)
        )

        session.add(step_log1)
        session.add(step_log2)
        session.commit()

        # Tester la récupération des statuts
        statuses = get_scenarios_status_for_ej(session, ej.id)

        assert len(statuses) == 2

        # Vérifier le premier scénario (succès)
        status1 = next(s for s in statuses if s.scenario_id == scenario1.id)
        assert status1.status == "all_aa"
        assert status1.is_success is True

        # Vérifier le deuxième scénario (erreur)
        status2 = next(s for s in statuses if s.scenario_id == scenario2.id)
        assert status2.status == "error"
        assert status2.is_success is False

    def test_get_scenarios_with_status_success_only(self, session: Session):
        """Test récupération scénarios avec statut spécifique - succès uniquement."""
        # Créer les données de test
        ej = EntiteJuridique(id=1, nom="Test EJ", finess="123456789")
        endpoint = SystemEndpoint(
            id=1,
            name="Test Endpoint",
            kind="MLLP",
            host="localhost",
            port=2575,
            entite_juridique_id=1
        )
        scenario = InteropScenario(
            id=1,
            key="success_scenario",
            name="Success Scenario",
            description="Scenario that succeeds",
            is_active=True
        )

        session.add(ej)
        session.add(endpoint)
        session.add(scenario)

        # Créer une exécution réussie
        run = ScenarioExecutionRun(
            id=1,
            scenario_id=1,
            endpoint_id=1,
            start_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc),
            status="completed"
        )
        step_log = ScenarioExecutionStepLog(
            id=1,
            run_id=1,
            step_name="Send Message",
            ack_code="AA",
            ack_message="Accepted",
            timestamp=datetime(2024, 1, 1, 10, 2, tzinfo=timezone.utc)
        )

        session.add(run)
        session.add(step_log)
        session.commit()

        # Tester la récupération des scénarios réussis
        success_scenarios = get_scenarios_with_status(session, "all_aa")

        assert len(success_scenarios) == 1
        scenario, status = success_scenarios[0]
        assert scenario.id == 1
        assert scenario.name == "Success Scenario"
        assert status.is_success is True

    def test_get_scenarios_with_status_no_results(self, session: Session):
        """Test récupération scénarios avec statut spécifique - aucun résultat."""
        # Tester avec un statut qui n'existe pas
        scenarios = get_scenarios_with_status(session, "nonexistent_status")

        assert len(scenarios) == 0

    def test_scenario_status_with_multiple_steps(self, session: Session):
        """Test statut scénario avec plusieurs étapes."""
        # Créer les données de test
        ej = EntiteJuridique(nom="Test EJ", finess="123456789")
        session.add(ej)
        session.flush()  # Pour obtenir l'ID généré

        endpoint = SystemEndpoint(
            name="Test Endpoint",
            kind="MLLP",
            host="localhost",
            port=2575,
            entite_juridique_id=ej.id
        )
        scenario = InteropScenario(
            key="test_scenario_key_multi",
            name="Multi-Step Scenario",
            description="Scenario with multiple steps",
            is_active=True
        )

        session.add(endpoint)
        session.add(scenario)
        session.flush()  # Pour obtenir les IDs générés

        # Créer une exécution avec plusieurs étapes
        run = ScenarioExecutionRun(
            scenario_id=scenario.id,
            endpoint_id=endpoint.id,
            start_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 10, 10, tzinfo=timezone.utc),
            status="completed"
        )
        session.add(run)
        session.flush()  # Pour obtenir l'ID généré

        # Étape 1: succès
        step_log1 = ScenarioExecutionStepLog(
            run_id=run.id,
            step_name="Step 1",
            ack_code="AA",
            ack_message="Accepted",
            timestamp=datetime(2024, 1, 1, 10, 2, tzinfo=timezone.utc)
        )
        # Étape 2: succès
        step_log2 = ScenarioExecutionStepLog(
            run_id=run.id,
            step_name="Step 2",
            ack_code="AA",
            ack_message="Accepted",
            timestamp=datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc)
        )
        # Étape 3: échec
        step_log3 = ScenarioExecutionStepLog(
            run_id=run.id,
            step_name="Step 3",
            ack_code="AE",
            ack_message="Error",
            timestamp=datetime(2024, 1, 1, 10, 8, tzinfo=timezone.utc)
        )

        session.add(step_log1)
        session.add(step_log2)
        session.add(step_log3)
        session.commit()

        # Tester le statut
        status = get_last_scenario_status(session, scenario.id, ej.id)
        assert status.is_success is False
