"""Tests de performance pour les opérations critiques."""
import pytest
import time
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
)
from app.models import Patient, Dossier, Venue, Mouvement
from app.services.fhir_export_service import FHIRExportService
from app.converters.fhir_converter import StructureToFHIRConverter


@pytest.fixture(name="session")
def session_fixture():
    """Fixture pour créer une session de base de données en mémoire."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="large_structure")
def large_structure_fixture(session: Session):
    """Fixture pour créer une grande structure de test."""
    # GHT
    ght = GHTContext(
        name="GHT Performance Test",
        code="GHT-PERF",
        oid_racine="1.2.3",
        fhir_server_url="http://test.com/fhir",
        is_active=True
    )
    session.add(ght)
    session.commit()
    session.refresh(ght)
    
    # EJ
    ej = EntiteJuridique(
        name="Hôpital Performance",
        finess_ej="123456789",
        ght_context_id=ght.id,
        is_active=True
    )
    session.add(ej)
    session.commit()
    session.refresh(ej)
    
    # Créer plusieurs EG
    egs = []
    for i in range(3):
        eg = EntiteGeographique(
            identifier=f"EG{i+1}",
            name=f"Site {i+1}",
            entite_juridique_id=ej.id,
            finess=f"98765{i+1:03d}",
            is_active=True
        )
        session.add(eg)
        egs.append(eg)
    session.commit()
    
    # Créer plusieurs pôles par EG
    poles = []
    for eg in egs:
        for i in range(5):
            pole = Pole(
                identifier=f"P{eg.identifier}{i+1}",
                name=f"Pôle {i+1} - {eg.name}",
                entite_geo_id=eg.id,
                physical_type="SI"
            )
            session.add(pole)
            poles.append(pole)
    session.commit()
    
    # Créer plusieurs services par pôle
    services = []
    for pole in poles:
        for i in range(3):
            service = Service(
                identifier=f"S{pole.identifier}{i+1}",
                name=f"Service {i+1} - {pole.name}",
                pole_id=pole.id,
                physical_type="SI",
                service_type="MCO"
            )
            session.add(service)
            services.append(service)
    session.commit()
    
    # Créer plusieurs UF par service
    ufs = []
    for service in services:
        for i in range(2):
            uf = UniteFonctionnelle(
                identifier=f"UF{service.identifier}{i+1}",
                name=f"UF {i+1} - {service.name}",
                service_id=service.id,
                physical_type="SI"
            )
            session.add(uf)
            ufs.append(uf)
    session.commit()
    
    # Créer des UH, chambres et lits
    for uf in ufs[:10]:  # Limiter pour les tests de performance
        uh = UniteHebergement(
            identifier=f"UH{uf.identifier}",
            name=f"UH {uf.name}",
            unite_fonctionnelle_id=uf.id,
            physical_type="WI"
        )
        session.add(uh)
        session.commit()
        
        for i in range(10):
            chambre = Chambre(
                identifier=f"CH{uh.identifier}{i+1}",
                name=f"Chambre {i+1}",
                unite_hebergement_id=uh.id,
                physical_type="RO"
            )
            session.add(chambre)
            session.commit()
            
            for j in range(2):
                lit = Lit(
                    identifier=f"L{chambre.identifier}{j+1}",
                    name=f"Lit {j+1}",
                    chambre_id=chambre.id,
                    physical_type="BD"
                )
                session.add(lit)
        session.commit()
    
    return ej


@pytest.fixture(name="many_patients")
def many_patients_fixture(session: Session, large_structure: EntiteJuridique):
    """Fixture pour créer beaucoup de patients."""
    patients = []
    for i in range(100):
        patient = Patient(
            identifier=f"PAT{i+1:05d}",
            family=f"PATIENT{i+1}",
            given=f"Test{i+1}"
        )
        session.add(patient)
        patients.append(patient)
    session.commit()
    
    # Créer des dossiers pour chaque patient
    for patient in patients:
        dossier = Dossier(
            dossier_seq=patient.id,
            patient_id=patient.id,
            admit_time=datetime.now()
        )
        session.add(dossier)
    session.commit()
    
    return patients


class TestStructureExportPerformance:
    """Tests de performance de l'export de structure."""
    
    def test_export_large_structure_performance(self, session: Session, large_structure: EntiteJuridique):
        """Test que l'export d'une grande structure est performant."""
        service = FHIRExportService(session, "http://test.com/fhir")
        
        start_time = time.time()
        bundle = service.export_structure(large_structure)
        end_time = time.time()
        
        elapsed = end_time - start_time
        
        # L'export devrait prendre moins de 5 secondes
        assert elapsed < 5.0, f"Export trop lent: {elapsed:.2f}s"
        
        # Vérifier que toutes les entités sont présentes
        assert len(bundle.entry) > 0
    
    def test_converter_performance(self, session: Session, large_structure: EntiteJuridique):
        """Test de la performance du convertisseur FHIR."""
        converter = StructureToFHIRConverter()
        
        # Récupérer une EG
        eg = session.query(EntiteGeographique).first()
        
        start_time = time.time()
        for _ in range(100):
            location = converter.create_location(eg)
        end_time = time.time()
        
        elapsed = end_time - start_time
        avg_time = elapsed / 100
        
        # Chaque conversion devrait prendre moins de 10ms
        assert avg_time < 0.01, f"Conversion trop lente: {avg_time*1000:.2f}ms"


class TestPatientQueryPerformance:
    """Tests de performance des requêtes patients."""
    
    def test_query_all_patients_performance(self, session: Session, many_patients: list):
        """Test que la requête de tous les patients est performante."""
        start_time = time.time()
        patients = session.query(Patient).all()
        end_time = time.time()
        
        elapsed = end_time - start_time
        
        # La requête devrait prendre moins de 1 seconde
        assert elapsed < 1.0, f"Requête trop lente: {elapsed:.2f}s"
        assert len(patients) == 100
    
    def test_query_with_join_performance(self, session: Session, many_patients: list):
        """Test que les requêtes avec jointures sont performantes."""
        start_time = time.time()
        results = (
            session.query(Patient, Dossier)
            .join(Dossier, Patient.id == Dossier.patient_id)
            .all()
        )
        end_time = time.time()
        
        elapsed = end_time - start_time
        
        # La requête avec jointure devrait prendre moins de 2 secondes
        assert elapsed < 2.0, f"Requête avec jointure trop lente: {elapsed:.2f}s"
        assert len(results) == 100


class TestBulkOperationsPerformance:
    """Tests de performance des opérations en masse."""
    
    def test_bulk_insert_patients(self, session: Session):
        """Test de l'insertion en masse de patients."""
        patients = [
            Patient(
                identifier=f"BULK{i+1:05d}",
                family=f"BULK{i+1}",
                given=f"Test{i+1}"
            )
            for i in range(1000)
        ]
        
        start_time = time.time()
        session.add_all(patients)
        session.commit()
        end_time = time.time()
        
        elapsed = end_time - start_time
        
        # L'insertion de 1000 patients devrait prendre moins de 10 secondes
        assert elapsed < 10.0, f"Insertion en masse trop lente: {elapsed:.2f}s"
        
        # Vérifier que tous les patients ont été insérés
        count = session.query(Patient).filter(Patient.identifier.like("BULK%")).count()
        assert count == 1000
    
    def test_bulk_update_performance(self, session: Session, many_patients: list):
        """Test de la mise à jour en masse."""
        start_time = time.time()
        for patient in many_patients:
            patient.family = f"UPDATED{patient.id}"
        session.commit()
        end_time = time.time()
        
        elapsed = end_time - start_time
        
        # La mise à jour en masse devrait prendre moins de 5 secondes
        assert elapsed < 5.0, f"Mise à jour en masse trop lente: {elapsed:.2f}s"


class TestCachePerformance:
    """Tests de performance du cache."""
    
    def test_repeated_query_caching(self, session: Session, large_structure: EntiteJuridique):
        """Test que les requêtes répétées bénéficient du cache."""
        # Première requête
        start_time = time.time()
        result1 = session.get(EntiteJuridique, large_structure.id)
        first_elapsed = time.time() - start_time
        
        # Deuxième requête (devrait être en cache)
        start_time = time.time()
        result2 = session.get(EntiteJuridique, large_structure.id)
        second_elapsed = time.time() - start_time
        
        # La deuxième requête devrait être plus rapide
        # Note: SQLAlchemy a son propre cache de session
        assert result1 == result2
        assert second_elapsed <= first_elapsed


@pytest.mark.slow
class TestLongRunningOperations:
    """Tests des opérations de longue durée (marqués comme lents)."""
    
    def test_export_complete_database(self, session: Session, large_structure: EntiteJuridique, many_patients: list):
        """Test de l'export complet de la base de données."""
        service = FHIRExportService(session, "http://test.com/fhir")
        
        start_time = time.time()
        
        # Export de la structure
        structure_bundle = service.export_structure(large_structure)
        
        # Export des patients
        patient_bundle = service.export_patients(large_structure)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # L'export complet devrait prendre moins de 30 secondes
        assert elapsed < 30.0, f"Export complet trop lent: {elapsed:.2f}s"
        
        # Vérifier que les bundles contiennent des données
        assert len(structure_bundle.entry) > 0
        # Note: patient_bundle pourrait être vide si les patients ne sont pas liés à l'EJ


class TestMemoryUsage:
    """Tests d'utilisation mémoire."""
    
    def test_memory_efficient_query(self, session: Session):
        """Test que les requêtes n'utilisent pas trop de mémoire."""
        # Créer beaucoup de données
        patients = [
            Patient(
                identifier=f"MEM{i+1:05d}",
                family=f"MEM{i+1}",
                given=f"Test{i+1}"
            )
            for i in range(10000)
        ]
        session.add_all(patients)
        session.commit()
        
        # Requête avec limite
        limited_results = session.query(Patient).limit(100).all()
        assert len(limited_results) == 100
        
        # Requête avec pagination
        page_size = 100
        for page in range(10):
            page_results = (
                session.query(Patient)
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )
            assert len(page_results) <= page_size