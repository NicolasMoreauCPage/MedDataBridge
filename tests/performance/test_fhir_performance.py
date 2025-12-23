# tests/performance/test_fhir_performance.py
"""
Tests de performance pour FHIR
Tests d'export/import de gros volumes et requêtes complexes
"""

import pytest
import time
from datetime import datetime
from sqlmodel import Session

from app.models import Patient, Dossier
from app.services.patients_service import PatientCreateSchema, create_patient
from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
from app.services.fhir_export_service import FHIRExportService
from app.services.fhir_import_service import FHIRImportService
from app.models_structure import GHTContext, EntiteJuridique


@pytest.mark.performance
class TestFHIRPerformance:
    """Tests de performance pour FHIR"""

    @pytest.mark.slow
    def test_fhir_bulk_export_patients(self, session: Session, sample_ght):
        """Test export FHIR de gros volumes de patients"""

        # Créer une EJ pour l'export
        ej = EntiteJuridique(
            name="Performance Test EJ",
            code="EJPERF",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Créer 500 patients
        patients = []
        start_time = time.time()

        for i in range(500):
            patient_data = PatientCreateSchema(
                family=f"PerfFamily{i:03d}",
                given=f"PerfGiven{i:03d}",
                birth_date=f"{1950 + (i % 50):04d}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
            )
            patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
            patients.append(patient)

        creation_time = time.time() - start_time
        print(f"Création de 500 patients: {creation_time:.2f}s")

        # Exporter tous les patients en FHIR
        export_service = FHIRExportService(session, "http://localhost:8000/fhir")
        start_time = time.time()

        patient_bundle = export_service.export_patients(ej)

        export_time = time.time() - start_time
        print(f"Export FHIR de 500 patients: {export_time:.2f}s")

        # Vérifications
        assert patient_bundle is not None
        assert len(patient_bundle.entry) >= 500
        assert export_time < 30, f"Export trop lent: {export_time:.2f}s pour 500 patients"

        # Vérifier la taille du bundle
        bundle_size = len(str(patient_bundle.model_dump())) / 1024 / 1024  # MB
        print(f"Taille du bundle: {bundle_size:.2f}MB")
        assert bundle_size < 50, f"Bundle trop volumineux: {bundle_size:.2f}MB"

    @pytest.mark.slow
    def test_fhir_bulk_export_with_dossiers(self, session: Session, sample_ght):
        """Test export FHIR avec dossiers et actes"""

        # Créer EJ
        ej = EntiteJuridique(
            name="Bulk Export Test",
            code="EJBULK",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Créer 100 patients avec dossiers
        start_time = time.time()

        for i in range(100):
            # Patient
            patient_data = PatientCreateSchema(
                family=f"BulkFamily{i:03d}",
                given=f"BulkGiven{i:03d}",
                birth_date=f"{1970 + (i % 30):04d}-01-01"
            )
            patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

            # Dossier
            dossier_data = DossierCreateSchema(
                uf_responsabilite="UF001",
                dossier_type="hospitalise",
                admit_time=datetime.now()
            )
            create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        setup_time = time.time() - start_time
        print(f"Création de 100 patients + dossiers: {setup_time:.2f}s")

        # Exporter
        export_service = FHIRExportService(session, "http://localhost:8000/fhir")
        start_time = time.time()

        patient_bundle = export_service.export_patients(ej)
        venue_bundle = export_service.export_venues(ej)

        export_time = time.time() - start_time
        print(f"Export FHIR patients + venues: {export_time:.2f}s")

        # Vérifications
        assert patient_bundle is not None
        assert venue_bundle is not None
        assert len(patient_bundle.entry) >= 100
        assert len(venue_bundle.entry) >= 100  # Au moins une venue par dossier
        assert export_time < 20, f"Export trop lent: {export_time:.2f}s"

    @pytest.mark.slow
    def test_fhir_complex_queries_performance(self, session: Session, sample_ght):
        """Test performance des requêtes FHIR complexes"""

        # Créer EJ
        ej = EntiteJuridique(
            name="Complex Query Test",
            code="EJQUERY",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Créer des données variées
        patients_data = [
            ("Dupont", "Jean", "1980-01-01", "M", "Paris"),
            ("Martin", "Marie", "1990-05-15", "F", "Lyon"),
            ("Dubois", "Pierre", "1975-12-20", "M", "Marseille"),
            ("Garcia", "Sophie", "1985-08-10", "F", "Toulouse"),
            ("Lefebvre", "Michel", "1960-03-25", "M", "Nice"),
        ] * 50  # 250 patients

        patients = []
        for family, given, birth_date, gender, city in patients_data:
            patient_data = PatientCreateSchema(
                family=family,
                given=given,
                birth_date=birth_date,
                gender=gender,
                city=city
            )
            patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
            patients.append(patient)

        # Test export avec filtres (simulé via service)
        export_service = FHIRExportService(session, "http://localhost:8000/fhir")

        # Mesurer export complet
        start_time = time.time()
        full_bundle = export_service.export_patients(ej)
        full_export_time = time.time() - start_time

        print(f"Export complet de 250 patients: {full_export_time:.2f}s")

        # Vérifier que l'export contient tous les patients
        assert len(full_bundle.entry) >= 250
        assert full_export_time < 15, f"Export complet trop lent: {full_export_time:.2f}s"

        # Test recherche par critères (simulé)
        # En pratique, ceci dépendrait de l'implémentation des filtres FHIR
        search_start = time.time()
        matching_patients = [p for p in full_bundle.entry
                           if p.resource.resourceType == "Patient"
                           and hasattr(p.resource, 'name')
                           and p.resource.name[0].family == "Dupont"]
        search_time = time.time() - search_start

        print(f"Recherche patients Dupont: {search_time:.4f}s, trouvés: {len(matching_patients)}")

        # La recherche devrait être rapide
        assert search_time < 0.1, f"Recherche trop lente: {search_time:.4f}s"
        assert len(matching_patients) == 50  # 50 Dupont

    @pytest.mark.slow
    def test_fhir_memory_usage_large_export(self, session: Session, sample_ght):
        """Test utilisation mémoire lors d'export FHIR volumineux"""

        import psutil
        import os

        # Créer EJ
        ej = EntiteJuridique(
            name="Memory Test EJ",
            code="EJMEM",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Créer 1000 patients
        for i in range(1000):
            patient_data = PatientCreateSchema(
                family=f"MemFamily{i:04d}",
                given=f"MemGiven{i:04d}",
                birth_date="1980-01-01"
            )
            create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Mesurer utilisation mémoire
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        export_service = FHIRExportService(session, "http://localhost:8000/fhir")
        start_time = time.time()

        bundle = export_service.export_patients(ej)

        export_time = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print(f"Export 1000 patients - Temps: {export_time:.2f}s, Mémoire: {memory_increase:.2f}MB")

        # Vérifications
        assert bundle is not None
        assert len(bundle.entry) >= 1000
        assert export_time < 60, f"Export trop lent: {export_time:.2f}s"
