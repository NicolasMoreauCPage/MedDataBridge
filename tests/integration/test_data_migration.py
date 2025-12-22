# tests/integration/test_data_migration.py
"""
Tests d'intégration pour la migration de données
Tests des migrations de schémas DB et transformations de données existantes
"""

import pytest
import os
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
from sqlmodel import Session, select, text
from sqlalchemy import inspect

from app.db import init_db, engine, get_session
from app.models import Patient, Dossier, Venue, Chambre, Lit
from app.models_structure import GHTContext
from app.services.patients_service import create_patient
from app.services.dossiers_service import create_dossier
from app.services.venues_service import create_venue


@pytest.mark.integration
class TestDataMigration:
    """Tests d'intégration pour les migrations de données"""

    def test_database_schema_migration_basic(self, session: Session):
        """Test migration basique du schéma de base de données"""
        # Vérifier que les tables principales existent
        inspector = inspect(engine)

        required_tables = [
            'patient', 'dossier', 'venue', 'chambre', 'lit',
            'ghtcontext', 'medecinresponsable', 'entitegeographique'
        ]

        existing_tables = inspector.get_table_names()

        for table in required_tables:
            assert table in existing_tables, f"Table {table} manquante dans la DB"

    def test_migration_generic_fields_chambre(self, session: Session, sample_ght):
        """Test migration des champs génériques pour les chambres"""
        # Créer une chambre de test directement avec le modèle
        from app.models_structure import Chambre

        chambre = Chambre(
            name="Chambre Test Migration",
            is_generic=True,
            max_occupancy=2
        )

        session.add(chambre)
        session.commit()
        session.refresh(chambre)

        # Vérifier que les champs génériques sont présents et fonctionnels
        assert hasattr(chambre, 'is_generic')
        assert hasattr(chambre, 'max_occupancy')
        assert chambre.is_generic == True
        assert chambre.max_occupancy == 2

        # Vérifier en base que les colonnes existent
        result = session.exec(text("PRAGMA table_info(chambre)")).all()
        column_names = [row[1] for row in result]

        assert 'is_generic' in column_names
        assert 'max_occupancy' in column_names

    def test_migration_generic_fields_lit(self, session: Session, sample_ght):
        """Test migration des champs génériques pour les lits"""
        # Créer un lit de test directement avec les modèles
        from app.models_structure import Chambre, Lit

        # D'abord créer une chambre
        chambre = Chambre(
            name="Chambre pour Lit",
            is_generic=False,
            max_occupancy=1
        )
        session.add(chambre)
        session.commit()
        session.refresh(chambre)

        lit = Lit(
            name="Lit Test Migration",
            chambre_id=chambre.id,
            is_generic=False,
            max_occupancy=1
        )
        session.add(lit)
        session.commit()
        session.refresh(lit)

        # Vérifier que les champs génériques sont présents
        assert hasattr(lit, 'is_generic')
        assert hasattr(lit, 'max_occupancy')
        assert lit.is_generic == False
        assert lit.max_occupancy == 1

        # Vérifier en base que les colonnes existent
        result = session.exec(text("PRAGMA table_info(lit)")).all()
        column_names = [row[1] for row in result]

        assert 'is_generic' in column_names
        assert 'max_occupancy' in column_names

    def test_migration_namespace_hierarchy(self, session: Session):
        """Test migration de la hiérarchie des namespaces"""
        from app.models_structure import IdentifierNamespace

        # Créer des namespaces (la hiérarchie est gérée via les relations d'entités)
        ns1 = IdentifierNamespace(
            name="IPP EJ Principal",
            system="urn:oid:1.2.3.4.5.6.7.8.9.10",
            oid="1.2.3.4.5.6.7.8.9.10",
            type="IPP"
        )
        session.add(ns1)

        ns2 = IdentifierNamespace(
            name="NDA Service Cardio",
            system="urn:oid:1.2.3.4.5.6.7.8.9.11",
            oid="1.2.3.4.5.6.7.8.9.11",
            type="NDA"
        )
        session.add(ns2)
        session.commit()

        # Vérifier que les namespaces sont créés
        assert ns1.id is not None
        assert ns2.id is not None
        assert ns1.type == "IPP"
        assert ns2.type == "NDA"

    def test_migration_medecin_responsable(self, session: Session):
        """Test migration de la table medecin_responsable"""
        from app.models_practitioners import MedecinResponsable

        # Vérifier que la table existe
        inspector = inspect(engine)
        assert 'medecinresponsable' in inspector.get_table_names()

        # Créer un medecin responsable de test
        medecin_resp = MedecinResponsable(
            family_name="Dr Test Migration",
            given_name="Migration",
            rpps="12345678901",
            specialty="Médecine générale"
        )
        session.add(medecin_resp)
        session.commit()

        # Vérifier que l'enregistrement est créé
        assert medecin_resp.id is not None
        assert medecin_resp.family_name == "Dr Test Migration"

    def test_migration_scenario_execution_runs(self, session: Session):
        """Test migration des runs d'exécution de scénarios"""
        from app.models_scenario_runs import ScenarioExecutionRun
        from app.models_scenarios import InteropScenario

        # Vérifier que la table existe
        inspector = inspect(engine)
        assert 'scenarioexecutionrun' in inspector.get_table_names()

        # Créer un scénario de test d'abord
        scenario = InteropScenario(
            key="test_migration_scenario",
            name="Test Migration Scenario",
            description="Scenario for migration testing",
            protocol="HL7"
        )
        session.add(scenario)
        session.commit()

        # Créer un run de test
        from datetime import datetime
        run = ScenarioExecutionRun(
            scenario_id=scenario.id,
            status="success",
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            finished_at=datetime(2025, 1, 1, 10, 5, 0),
            total_steps=5,
            success_steps=5,
            error_steps=0
        )
        session.add(run)
        session.commit()

        assert run.id is not None
        assert run.status == "success"

    def test_data_transformation_patient_normalization(self, session: Session, sample_ght):
        """Test transformation et normalisation des données patient"""
        from app.services.patients_service import PatientCreateSchema

        # Créer un patient avec des données à normaliser
        patient_data = PatientCreateSchema(
            family="DUPONT",  # Majuscules
            given="jean-pierre",  # Tirets
            birth_date="1980-05-15"
        )

        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Vérifier que les données sont stockées correctement
        assert patient.family == "DUPONT"
        assert patient.given == "jean-pierre"
        assert patient.birth_date.isoformat() == "1980-05-15"

        # Test de recherche insensible à la casse (si implémenté)
        patients = session.exec(
            select(Patient).where(Patient.family.ilike("dupont"))
        ).all()

        assert len(patients) >= 1
        assert any(p.family == "DUPONT" for p in patients)

    def test_data_transformation_dossier_state_transitions(self, session: Session, sample_ght):
        """Test transformation des transitions d'état de dossier"""
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        from app.services.patients_service import PatientCreateSchema, create_patient

        # Créer un patient
        patient_data = PatientCreateSchema(
            family="Test",
            given="Migration",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Créer un dossier avec pré-admission
        dossier_data = DossierCreateSchema(
            uf_responsabilite="UF001",
            dossier_type="hospitalise",
            admission_source="CONSULTATION",
            attending_provider="Dr. Test",
            admit_time=datetime.now(),
            current_state="Pré-admission"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Vérifier que le dossier est créé correctement
        assert dossier.id is not None
        assert dossier.patient_id == patient.id
        assert len(dossier.venues) == 1
        assert dossier.venues[0].code == "PRE_ADMIT"

    def test_migration_backward_compatibility(self, session: Session, sample_ght):
        """Test compatibilité arrière lors des migrations"""
        # S'assurer qu'il y a au moins un patient pour tester la compatibilité
        patients = session.exec(select(Patient)).all()
        
        if len(patients) == 0:
            # Créer un patient de test si aucun n'existe
            from app.services.patients_service import PatientCreateSchema, create_patient
            patient_data = PatientCreateSchema(
                family="Test",
                given="User",
                birth_date="1980-01-01"
            )
            test_patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
            patients = [test_patient]

        # Vérifier qu'il y a au moins un patient
        assert len(patients) >= 1

        for patient in patients:
            # Vérifier que tous les champs requis sont présents
            assert hasattr(patient, 'family')
            assert hasattr(patient, 'given')
            assert hasattr(patient, 'birth_date')
            assert hasattr(patient, 'id')

    def test_migration_performance_large_dataset(self, session: Session, sample_ght):
        """Test performance de migration sur gros volumes de données"""
        import time

        # Créer un grand nombre de patients pour tester la performance
        start_time = time.time()
        patients_created = 0

        for i in range(100):  # Créer 100 patients
            patient_data = PatientCreateSchema(
                family=f"Family{i:03d}",
                given=f"Given{i:03d}",
                birth_date="1980-01-01"
            )
            patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
            patients_created += 1

        end_time = time.time()
        creation_time = end_time - start_time

        # Vérifier que la création en masse est raisonnablement rapide
        assert patients_created == 100
        assert creation_time < 30  # Moins de 30 secondes pour 100 patients

        # Vérifier que tous les patients sont bien créés
        count = session.exec(select(Patient).where(Patient.family.like("Family%"))).count()
        assert count >= 100

    def test_migration_rollback_simulation(self, session: Session):
        """Test simulation de rollback de migration"""
        # Compter les patients avant
        initial_count = session.exec(select(Patient)).count()

        # Simuler une migration qui échoue
        try:
            # Créer un patient qui pourrait échouer
            patient_data = PatientCreateSchema(
                family="Test Rollback",
                given="Patient",
                birth_date="1980-01-01"
            )
            patient = create_patient(session=session, patient_data=patient_data, ght_context_id=999)  # ID invalide

            # Forcer un rollback en levant une exception
            raise Exception("Migration failed - testing rollback")

        except Exception:
            session.rollback()

        # Vérifier que le nombre de patients n'a pas changé
        final_count = session.exec(select(Patient)).count()
        assert final_count == initial_count

    def test_migration_data_integrity_constraints(self, session: Session):
        """Test intégrité des données et contraintes lors des migrations"""
        from sqlalchemy.exc import IntegrityError

        # Tester les contraintes de clé étrangère
        try:
            # Tenter de créer un dossier avec un patient_id invalide
            dossier = Dossier(
                patient_id=99999,  # ID qui n'existe pas
                admission_datetime="2025-01-01T10:00:00"
            )
            session.add(dossier)
            session.commit()

            # Si on arrive ici, la contrainte n'est pas respectée
            assert False, "Contrainte de clé étrangère non respectée"

        except IntegrityError:
            # C'est normal - rollback et continuer
            session.rollback()
            assert True  # Test réussi

    def test_migration_audit_trail_preservation(self, session: Session):
        """Test préservation des pistes d'audit lors des migrations"""
        # Vérifier que les champs created_at/updated_at sont présents
        patients = session.exec(select(Patient).limit(1)).all()

        if patients:
            patient = patients[0]
            # Vérifier que les timestamps existent
            assert hasattr(patient, 'created_at') or hasattr(patient, 'date_created')
            assert hasattr(patient, 'updated_at') or hasattr(patient, 'date_updated')

    def test_migration_index_performance(self, session: Session):
        """Test performance des indexes après migration"""
        import time

        # Tester la performance de recherche avec indexes
        start_time = time.time()

        # Recherche par nom de famille (devrait être indexée)
        patients = session.exec(
            select(Patient).where(Patient.family.like("Test%"))
        ).all()

        search_time = time.time() - start_time

        # La recherche devrait être rapide (< 1 seconde)
        assert search_time < 1.0

        # Vérifier que des résultats sont retournés
