# tests/integration/test_data_migration.py
"""
Tests d'intégration pour la migration de données
Tests des migrations de schémas DB et transformations de données existantes
"""

import pytest
import os
import tempfile
from pathlib import Path
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
            'ghtcontext', 'medecin', 'entitegeographique'
        ]

        existing_tables = inspector.get_table_names()

        for table in required_tables:
            assert table in existing_tables, f"Table {table} manquante dans la DB"

    def test_migration_generic_fields_chambre(self, session: Session, sample_ght):
        """Test migration des champs génériques pour les chambres"""
        # Créer une chambre de test
        from app.services.venues_service import create_chambre

        chambre_data = {
            "name": "Chambre Test Migration",
            "venue_id": None,  # Chambre générique
            "is_generic": True,
            "max_occupancy": 2
        }

        chambre = create_chambre(session=session, chambre_data=chambre_data, ght_context_id=sample_ght.id)

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
        # Créer un lit de test
        from app.services.venues_service import create_lit

        # D'abord créer une chambre
        from app.services.venues_service import create_chambre
        chambre = create_chambre(session=session, chambre_data={
            "name": "Chambre pour Lit",
            "is_generic": False,
            "max_occupancy": 1
        }, ght_context_id=sample_ght.id)

        lit_data = {
            "name": "Lit Test Migration",
            "chambre_id": chambre.id,
            "is_generic": False,
            "max_occupancy": 1
        }

        lit = create_lit(session=session, lit_data=lit_data, ght_context_id=sample_ght.id)

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
        from app.models_identifiers import IdentifierNamespace

        # Créer une hiérarchie de namespaces
        root_ns = IdentifierNamespace(
            name="Root Namespace",
            code="ROOT",
            parent_id=None
        )
        session.add(root_ns)

        child_ns = IdentifierNamespace(
            name="Child Namespace",
            code="CHILD",
            parent_id=root_ns.id
        )
        session.add(child_ns)
        session.commit()

        # Vérifier que la hiérarchie fonctionne
        assert root_ns.parent_id is None
        assert child_ns.parent_id == root_ns.id

        # Vérifier les colonnes de hiérarchie
        result = session.exec(text("PRAGMA table_info(identifiernamespace)")).all()
        column_names = [row[1] for row in result]

        assert 'parent_id' in column_names
        assert 'hierarchy_level' in column_names

    def test_migration_medecin_responsable(self, session: Session):
        """Test migration de la table medecin_responsable"""
        from app.models_practitioners import MedecinResponsable

        # Vérifier que la table existe
        inspector = inspect(engine)
        assert 'medecinresponsable' in inspector.get_table_names()

        # Créer un medecin responsable de test
        medecin_resp = MedecinResponsable(
            nom="Dr Test Migration",
            prenom="Migration",
            rpps="12345678901",
            speciality="Médecine générale"
        )
        session.add(medecin_resp)
        session.commit()

        # Vérifier que l'enregistrement est créé
        assert medecin_resp.id is not None
        assert medecin_resp.nom == "Dr Test Migration"

    def test_migration_scenario_execution_runs(self, session: Session):
        """Test migration des runs d'exécution de scénarios"""
        from app.models_scenario_runs import ScenarioExecutionRun

        # Vérifier que la table existe
        inspector = inspect(engine)
        assert 'scenarioexecutionrun' in inspector.get_table_names()

        # Créer un run de test
        run = ScenarioExecutionRun(
            scenario_name="Test Migration Scenario",
            status="completed",
            start_time="2025-01-01T10:00:00",
            end_time="2025-01-01T10:05:00",
            total_steps=5,
            successful_steps=5,
            failed_steps=0
        )
        session.add(run)
        session.commit()

        assert run.id is not None
        assert run.status == "completed"

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
        from app.services.dossiers_service import DossierCreateSchema, update_dossier_state
        from app.models import Mouvement

        # Créer un patient et un dossier
        patient_data = PatientCreateSchema(
            family="Test",
            given="Migration",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            patient_id=patient.id,
            admission_datetime="2025-01-01T10:00:00"
        )
        dossier = create_dossier(session=session, dossier_data=dossier_data, ght_context_id=sample_ght.id)

        # Créer un mouvement d'admission
        venue = session.exec(select(Venue)).first()
        if not venue:
            venue = create_venue(session=session, venue_data={
                "name": "Venue Test Migration",
                "venue_type": "HOSPITALISE"
            }, ght_context_id=sample_ght.id)

        mouvement = Mouvement(
            dossier_id=dossier.id,
            venue_id=venue.id,
            mouvement_type="ADMISSION",
            start_datetime="2025-01-01T10:00:00"
        )
        session.add(mouvement)
        session.commit()

        # Vérifier que l'état du dossier est mis à jour correctement
        updated_dossier = update_dossier_state(session, dossier.id)
        assert updated_dossier.current_venue_id == venue.id

    def test_migration_backward_compatibility(self, session: Session):
        """Test compatibilité arrière lors des migrations"""
        # Vérifier que les anciennes données sont toujours accessibles
        patients = session.exec(select(Patient)).all()

        # Au minimum, il devrait y avoir le patient de test créé par conftest.py
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
        assert isinstance(patients, list)</content>
<parameter name="filePath">/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/tests/integration/test_data_migration.py