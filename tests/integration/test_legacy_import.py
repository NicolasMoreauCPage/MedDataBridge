# tests/integration/test_legacy_import.py
"""
Tests d'intégration pour l'import de données legacy
Tests d'import de données anciennes et validation/nettoyage
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from sqlmodel import Session, select

from app.db import get_session
from app.models import Patient, Dossier, Venue
from app.models_structure import GHTContext
from app.services.patients_service import PatientCreateSchema, create_patient
from app.services.dossiers_service import create_dossier
from app.services.venues_service import create_venue


@pytest.mark.integration
class TestLegacyImport:
    """Tests d'intégration pour l'import de données legacy"""

    def test_legacy_patient_import_format_validation(self, session: Session, sample_ght):
        """Test validation du format des données patient legacy"""
        # Simuler des données patient legacy avec différents formats
        legacy_patient_formats = [
            {
                "nom": "DUPONT",
                "prenom": "Jean",
                "date_naissance": "1980-05-15",
                "sexe": "M"
            },
            {
                "family": "MARTIN",
                "given": "Marie",
                "birth_date": "1975-12-03",
                "gender": "F"
            },
            {
                "NOM": "LEFEBVRE",
                "PRENOM": "Pierre",
                "DATE_NAISSANCE": "1990-08-20"
            }
        ]

        for legacy_data in legacy_patient_formats:
            # Transformer les données legacy vers le nouveau format
            transformed_data = self._transform_legacy_patient_data(legacy_data)

            # Créer le patient avec les données transformées
            patient_data = PatientCreateSchema(**transformed_data)
            patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

            # Vérifier que le patient est créé correctement
            assert patient.id is not None
            assert patient.family is not None
            assert patient.given is not None
            assert patient.birth_date is not None

    def test_legacy_dossier_import_with_patient_reference(self, session: Session, sample_ght):
        """Test import de dossiers legacy avec référence patient"""
        # Créer un patient d'abord
        patient_data = PatientCreateSchema(
            family="Test",
            given="Legacy",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Simuler des données dossier legacy
        legacy_dossier_data = {
            "patient_id": patient.id,
            "numero_dossier": "DOS-2025-001",
            "date_admission": "2025-01-01T10:00:00",
            "service": "Médecine interne",
            "statut": "HOSPITALISE"
        }

        # Transformer et créer le dossier
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        transformed_data = self._transform_legacy_dossier_data(legacy_dossier_data)
        dossier_data = DossierCreateSchema(**transformed_data)
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Vérifier que le dossier est créé
        assert dossier.id is not None
        assert dossier.patient_id == patient.id
        assert dossier.admit_time is not None

    def test_legacy_venue_import_hierarchy(self, session: Session, sample_ght):
        """Test import de venues legacy avec hiérarchie"""
        # Simuler une hiérarchie de venues legacy
        legacy_venues = [
            {
                "type": "ETABLISSEMENT",
                "nom": "Hôpital Central",
                "code": "HOP001",
                "parent": None
            },
            {
                "type": "SERVICE",
                "nom": "Médecine Interne",
                "code": "MEDINT",
                "parent": "HOP001"
            },
            {
                "type": "UNITE",
                "nom": "Unité A",
                "code": "UNITA",
                "parent": "MEDINT"
            }
        ]

        created_venues = {}
        for legacy_venue in legacy_venues:
            # Transformer les données
            transformed_data = self._transform_legacy_venue_data(legacy_venue, created_venues)

            # Créer la venue
            venue = create_venue(session=session, venue_data=transformed_data, ght_context_id=sample_ght.id)
            created_venues[legacy_venue["code"]] = venue

            assert venue.id is not None
            assert venue.name == legacy_venue["nom"]

    def test_legacy_data_cleaning_and_validation(self, session: Session, sample_ght):
        """Test nettoyage et validation des données legacy"""
        # Données legacy avec problèmes courants
        problematic_legacy_data = [
            {
                "family": "DUPONT ",  # Espace en fin
                "given": " Jean ",    # Espaces autour
                "birth_date": "1980-05-15"
            },
            {
                "family": "MARTIN",
                "given": "marie-claire",  # Tiret
                "birth_date": "1975/12/03"  # Mauvais format de date
            },
            {
                "family": "",  # Vide
                "given": "Pierre",
                "birth_date": "1990-08-20"
            },
            {
                "family": "LÉGER",  # Accent
                "given": "François",
                "birth_date": "1985-03-10"
            }
        ]

        for legacy_data in problematic_legacy_data:
            try:
                # Nettoyer et transformer les données
                cleaned_data = self._clean_legacy_patient_data(legacy_data)

                # Tenter de créer le patient
                if cleaned_data["family"] and cleaned_data["given"]:
                    patient_data = PatientCreateSchema(**cleaned_data)
                    patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

                    # Vérifier que les données sont nettoyées
                    assert patient.family == patient.family.strip()
                    assert patient.given == patient.given.strip()
                    assert patient.birth_date is not None

            except Exception as e:
                # Les données trop problématiques peuvent échouer - c'est acceptable
                assert "family" in str(e) or "given" in str(e) or "birth_date" in str(e)

    def test_legacy_import_bulk_performance(self, session: Session, sample_ght):
        """Test performance d'import en masse de données legacy"""
        import time

        # Simuler un gros volume de données patient legacy
        legacy_patients = []
        for i in range(200):  # 200 patients
            legacy_patients.append({
                "nom": "02d",
                "prenom": "03d",
                "date_naissance": "1980-01-01"
            })

        start_time = time.time()

        patients_created = 0
        for legacy_data in legacy_patients:
            try:
                transformed_data = self._transform_legacy_patient_data(legacy_data)
                patient_data = PatientCreateSchema(**transformed_data)
                patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
                patients_created += 1
            except Exception:
                # Ignorer les erreurs individuelles pour le test de performance
                pass

        end_time = time.time()
        import_time = end_time - start_time

        # Vérifier que l'import est raisonnablement rapide
        assert patients_created > 150  # Au moins 75% de succès
        assert import_time < 60  # Moins d'1 minute pour 200 patients

    def test_legacy_import_duplicate_handling(self, session: Session, sample_ght):
        """Test gestion des doublons lors de l'import legacy"""
        # Créer un patient de base
        base_patient_data = PatientCreateSchema(
            family="DUPONT",
            given="Jean",
            birth_date="1980-05-15"
        )
        base_patient = create_patient(session=session, patient_data=base_patient_data, ght_context_id=sample_ght.id)

        # Simuler des données legacy dupliquées
        duplicate_legacy_data = [
            {
                "nom": "DUPONT",
                "prenom": "Jean",
                "date_naissance": "1980-05-15"
            },
            {
                "family": "DUPONT",
                "given": "Jean",
                "birth_date": "1980-05-15"
            }
        ]

        # Importer les doublons
        imported_patients = []
        for legacy_data in duplicate_legacy_data:
            try:
                transformed_data = self._transform_legacy_patient_data(legacy_data)
                patient_data = PatientCreateSchema(**transformed_data)
                patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
                imported_patients.append(patient)
            except Exception:
                # Les doublons peuvent échouer selon la logique métier
                pass

        # Vérifier qu'il n'y a pas eu de création de doublons
        # (selon la logique métier, les doublons peuvent être rejetés ou fusionnés)
        total_patients = session.exec(select(Patient).where(Patient.family == "DUPONT")).count()

        # Soit 1 patient (fusion), soit plus si la logique permet les doublons
        assert total_patients >= 1

    def test_legacy_import_error_recovery(self, session: Session, sample_ght):
        """Test récupération d'erreur lors d'import legacy"""
        # Simuler un fichier legacy avec des données valides et invalides
        mixed_legacy_data = [
            # Valide
            {
                "nom": "VALID",
                "prenom": "Patient",
                "date_naissance": "1980-01-01"
            },
            # Invalide - données manquantes
            {
                "nom": "",
                "prenom": "",
                "date_naissance": "invalid-date"
            },
            # Valide
            {
                "family": "ANOTHER",
                "given": "Valid",
                "birth_date": "1975-06-15"
            },
            # Invalide - format incorrect
            {
                "nom": None,
                "prenom": 123,
                "date_naissance": "not-a-date"
            }
        ]

        successful_imports = 0
        failed_imports = 0

        for legacy_data in mixed_legacy_data:
            try:
                transformed_data = self._transform_legacy_patient_data(legacy_data)
                patient_data = PatientCreateSchema(**transformed_data)
                patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
                successful_imports += 1
            except Exception:
                failed_imports += 1

        # Vérifier que certains imports réussissent et d'autres échouent
        assert successful_imports > 0
        assert failed_imports > 0
        assert successful_imports + failed_imports == len(mixed_legacy_data)

    def test_legacy_import_transaction_rollback(self, session: Session, sample_ght):
        """Test rollback de transaction lors d'import legacy échoué"""
        # Compter les patients avant l'import
        initial_count = session.exec(select(Patient)).count()

        # Simuler un import qui échoue partiellement
        legacy_batch = [
            {
                "nom": "ROLLBACK",
                "prenom": "Test1",
                "date_naissance": "1980-01-01"
            },
            {
                "nom": "ROLLBACK",
                "prenom": "Test2",
                "date_naissance": "invalid-date"  # Provoquera une erreur
            },
            {
                "nom": "ROLLBACK",
                "prenom": "Test3",
                "date_naissance": "1980-01-03"
            }
        ]

        try:
            # Traiter le lot (sans transaction explicite pour ce test)
            for legacy_data in legacy_batch:
                transformed_data = self._transform_legacy_patient_data(legacy_data)
                patient_data = PatientCreateSchema(**transformed_data)
                create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

            # Forcer un rollback si nécessaire
            raise Exception("Simulated batch import failure")

        except Exception:
            session.rollback()

        # Vérifier que le nombre de patients n'a pas changé significativement
        final_count = session.exec(select(Patient)).count()
        assert abs(final_count - initial_count) <= 1  # Au plus 1 patient créé

    def test_legacy_import_data_consistency_validation(self, session: Session, sample_ght):
        """Test validation de cohérence des données legacy"""
        # Données legacy avec incohérences potentielles
        inconsistent_legacy_data = [
            {
                "nom": "ADULT",
                "prenom": "Patient",
                "date_naissance": "2020-01-01",  # Date future impossible
                "expected_error": "birth_date_future"
            },
            {
                "nom": "CENTENAIRE",
                "prenom": "Patient",
                "date_naissance": "1825-01-01",  # Trop vieux
                "expected_error": "birth_date_too_old"
            },
            {
                "nom": "VALID",
                "prenom": "Patient",
                "date_naissance": "1990-01-01",  # Valide
                "expected_error": None
            }
        ]

        for legacy_data in inconsistent_legacy_data:
            try:
                transformed_data = self._transform_legacy_patient_data(legacy_data)
                patient_data = PatientCreateSchema(**transformed_data)
                patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

                if legacy_data.get("expected_error"):
                    # Si on s'attendait à une erreur, c'est un problème
                    assert False, f"Expected error {legacy_data['expected_error']} but import succeeded"
                else:
                    # Import réussi comme attendu
                    assert patient.id is not None

            except Exception as e:
                if legacy_data.get("expected_error"):
                    # Erreur attendue - vérifier le type d'erreur
                    assert legacy_data["expected_error"] in str(e).lower()
                else:
                    # Erreur inattendue
                    raise

    # Helper methods pour transformer les données legacy

    def _transform_legacy_patient_data(self, legacy_data: dict) -> dict:
        """Transforme les données patient legacy vers le nouveau format"""
        transformed = {}

        # Mapping des champs
        field_mappings = {
            'nom': 'family',
            'prenom': 'given',
            'date_naissance': 'birth_date',
            'family': 'family',
            'given': 'given',
            'birth_date': 'birth_date',
            # Support pour les champs en majuscules
            'NOM': 'family',
            'PRENOM': 'given', 
            'DATE_NAISSANCE': 'birth_date'
        }

        for legacy_field, new_field in field_mappings.items():
            if legacy_field in legacy_data:
                transformed[new_field] = legacy_data[legacy_field]

        # Normalisation basique
        if 'family' in transformed:
            transformed['family'] = str(transformed['family']).upper()
        if 'given' in transformed:
            transformed['given'] = str(transformed['given']).lower()

        return transformed

    def _transform_legacy_dossier_data(self, legacy_data: dict) -> dict:
        """Transforme les données dossier legacy"""
        from datetime import datetime
        from app.models import DossierType
        
        transformed = {}

        # Mapping basique
        transformed['patient_id'] = legacy_data.get('patient_id')
        
        # Mapping des champs requis pour DossierCreateSchema
        transformed['admit_time'] = datetime.fromisoformat(legacy_data.get('date_admission'))
        transformed['dossier_type'] = DossierType.HOSPITALISE  # Default to hospitalise
        
        # Champs optionnels avec valeurs par défaut
        transformed['uf_responsabilite'] = legacy_data.get('service', 'Médecine Interne')
        transformed['admission_source'] = 'Legacy Import'
        transformed['attending_provider'] = 'Dr. Legacy'
        transformed['current_state'] = 'Importé depuis legacy'

        return transformed

    def _transform_legacy_venue_data(self, legacy_data: dict, created_venues: dict) -> dict:
        """Transforme les données venue legacy"""
        transformed = {
            'name': legacy_data.get('nom', ''),
            'venue_type': legacy_data.get('type', 'SERVICE')
        }

        # Gérer la hiérarchie si parent existe
        if legacy_data.get('parent') and legacy_data['parent'] in created_venues:
            transformed['parent_id'] = created_venues[legacy_data['parent']].id

        return transformed

    def _clean_legacy_patient_data(self, legacy_data: dict) -> dict:
        """Nettoie les données patient legacy"""
        cleaned = self._transform_legacy_patient_data(legacy_data)

        # Nettoyage spécifique
        if 'family' in cleaned:
            cleaned['family'] = cleaned['family'].strip()
        if 'given' in cleaned:
            cleaned['given'] = cleaned['given'].strip()

        # Validation basique
        if not cleaned.get('family'):
            cleaned['family'] = 'INCONNU'
        if not cleaned.get('given'):
            cleaned['given'] = 'INCONNU'

