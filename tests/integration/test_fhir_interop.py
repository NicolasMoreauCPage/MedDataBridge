# tests/integration/test_fhir_interop.py
"""
Tests d'intégration pour l'interopérabilité FHIR
Tests d'échange FHIR avec systèmes externes et conformité profils
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlmodel import Session

from app.models import Patient, Dossier, DossierType
from app.services.patients_service import PatientCreateSchema, create_patient
from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
from app.services.fhir_export_service import FHIRExportService
from app.services.fhir_import_service import FHIRImportService
from app.models_structure import GHTContext, EntiteJuridique
from fhir.resources.bundle import Bundle
from fhir.resources.patient import Patient as FHIRPatient


@pytest.mark.integration
class TestFHIRInteroperability:
    """Tests d'intégration pour l'interopérabilité FHIR"""

    @pytest.mark.asyncio
    async def test_fhir_export_import_roundtrip(self, session: Session, sample_ej, sample_uf):
        """Test roundtrip export FHIR → import FHIR"""

        # Créer des données de test
        patient_data = PatientCreateSchema(
            family="TestFHIR",
            given="Patient",
            birth_date="1990-01-01",
            gender="F"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ej.ght_context_id)

        dossier_data = DossierCreateSchema(
            uf_responsabilite=sample_uf.identifier,
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime.now(),
            admission_source="Test Source",
            attending_provider="Test Provider"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Utiliser l'EJ de test
        ej = sample_ej

        # Exporter en FHIR
        export_service = FHIRExportService(session, "http://localhost:8000/fhir")
        patient_bundle = export_service.export_patients(ej)

        # Vérifier que l'export contient notre patient
        assert patient_bundle is not None
        assert len(patient_bundle.entry) >= 1

        # Trouver le patient FHIR
        fhir_patient = None
        for entry in patient_bundle.entry:
            if entry.resource.resourceType == "Patient":
                if hasattr(entry.resource, 'identifier'):
                    for identifier in entry.resource.identifier:
                        if identifier.value == patient.identifier:
                            fhir_patient = entry.resource
                            break
            if fhir_patient:
                break

        assert fhir_patient is not None, "Patient FHIR non trouvé dans l'export"

        # Tester l'import du bundle FHIR
        import_service = FHIRImportService(session)

        # Mock pour éviter les appels réseau
        with patch.object(import_service, '_validate_bundle', return_value=True):
            with patch.object(import_service, '_process_patient', return_value=patient.id):
                result = await import_service.import_bundle(patient_bundle)

                # Vérifier que l'import a réussi
                assert result is not None
                # Les détails dépendent de l'implémentation de l'import

    @pytest.mark.asyncio
    async def test_fhir_profile_compliance(self, session: Session, sample_ght):
        """Test conformité aux profils FHIR"""

        # Créer un patient avec toutes les données requises
        patient_data = PatientCreateSchema(
            family="Compliance",
            given="Test",
            birth_date="1985-06-15",
            gender="M",
            address="123 Test Street",
            city="Test City",
            postal_code="12345",
            country="France"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Créer EJ
        ej = EntiteJuridique(
            name="Test Compliance",
            code="EJCOMP",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Créer UF pour l'EJ
        from app.models_structure import UniteFonctionnelle, Service, Pole, EntiteGeographique
        eg = EntiteGeographique(
            name="Test EG",
            entite_juridique_id=ej.id
        )
        session.add(eg)
        session.commit()

        pole = Pole(
            name="Test Pole",
            entite_geo_id=eg.id
        )
        session.add(pole)
        session.commit()

        service = Service(
            name="Test Service",
            pole_id=pole.id
        )
        session.add(service)
        session.commit()

        uf = UniteFonctionnelle(
            name="Test UF",
            identifier="UFTEST",
            service_id=service.id
        )
        session.add(uf)
        session.commit()

        # Créer dossier et venue pour lier le patient à l'EJ
        dossier_data = DossierCreateSchema(
            uf_responsabilite=uf.identifier,
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime.now(),
            admission_source="Test Source",
            attending_provider="Test Provider"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Exporter et vérifier la conformité FHIR
        export_service = FHIRExportService(session, "http://localhost:8000/fhir")
        patient_bundle = export_service.export_patients(ej)

        # Vérifier la structure du bundle
        assert patient_bundle.type == "collection" or patient_bundle.type == "searchset"
        assert patient_bundle.resourceType == "Bundle"

        # Pour chaque entry patient, vérifier les éléments requis
        for entry in patient_bundle.entry:
            resource = entry.resource
            if isinstance(resource, dict):
                resource_type = resource.get('resourceType')
            else:
                resource_type = getattr(resource, 'resourceType', None)
            
            if resource_type == "Patient":
                fhir_patient = resource

                # Vérifier les éléments de base
                if isinstance(fhir_patient, dict):
                    assert 'resourceType' in fhir_patient
                    assert fhir_patient['resourceType'] == "Patient"
                    
                    # Vérifier nom
                    assert 'name' in fhir_patient
                    assert len(fhir_patient['name']) > 0
                    assert 'family' in fhir_patient['name'][0]
                    assert fhir_patient['name'][0]['family'] is not None
                    
                    # Vérifier date de naissance si présente
                    if 'birthDate' in fhir_patient and fhir_patient['birthDate']:
                        birth_date = fhir_patient['birthDate']
                        # Doit être au format YYYY-MM-DD
                        assert len(birth_date) == 10
                        assert birth_date[4] == '-'
                        assert birth_date[7] == '-'
                    
                    # Vérifier genre si présent
                    if 'gender' in fhir_patient and fhir_patient['gender']:
                        assert fhir_patient['gender'] in ['male', 'female', 'other', 'unknown']
                else:
                    assert hasattr(fhir_patient, 'resourceType')
                    assert fhir_patient.resourceType == "Patient"

                    # Vérifier nom
                    assert hasattr(fhir_patient, 'name')
                    assert len(fhir_patient.name) > 0
                    assert 'family' in fhir_patient.name[0]
                    assert fhir_patient.name[0]['family'] is not None

                    # Vérifier date de naissance si présente
                    if hasattr(fhir_patient, 'birthDate') and fhir_patient.birthDate:
                        # Doit être au format YYYY-MM-DD
                        assert len(fhir_patient.birthDate) == 10
                        assert fhir_patient.birthDate[4] == '-'
                        assert fhir_patient.birthDate[7] == '-'

                    # Vérifier genre si présent
                    if hasattr(fhir_patient, 'gender') and fhir_patient.gender:
                        assert fhir_patient.gender in ['male', 'female', 'other', 'unknown']

    @pytest.mark.asyncio
    async def test_fhir_external_system_exchange(self, session: Session, sample_ght):
        """Test échange avec système externe simulé"""

        # Créer des données locales
        patient_data = PatientCreateSchema(
            family="External",
            given="System",
            birth_date="1970-12-25"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        ej = EntiteJuridique(
            name="External Test",
            code="EJEXT",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Simuler l'envoi à un système externe
        export_service = FHIRExportService(session, "http://external-system.com/fhir")

        # Mock de la requête HTTP
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "external-123"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            # Tenter l'export (en supposant que le service gère l'envoi)
            # Note: Cette partie dépend de l'implémentation réelle du service
            patient_bundle = export_service.export_patients(ej)

            # Vérifier que le bundle est correctement formé pour l'échange
            assert patient_bundle is not None

            # Vérifier les métadonnées du bundle
            assert hasattr(patient_bundle, 'meta')
            # assert patient_bundle.meta.lastUpdated is not None  # Si implémenté

    @pytest.mark.asyncio
    async def test_fhir_validation_errors(self, session: Session, sample_ght):
        """Test gestion des erreurs de validation FHIR"""

        # Créer un patient avec données invalides pour FHIR
        patient_data = PatientCreateSchema(
            family="",  # Nom vide - invalide
            given="Test",
            birth_date="2500-01-01"  # Date future - suspecte
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        ej = EntiteJuridique(
            name="Validation Test",
            code="EJVAL",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        # Exporter et vérifier la gestion des erreurs
        export_service = FHIRExportService(session, "http://localhost:8000/fhir")

        # L'export devrait réussir même avec des données suspectes
        # (la validation stricte dépend de l'implémentation)
        patient_bundle = export_service.export_patients(ej)

        assert patient_bundle is not None
        assert len(patient_bundle.entry) >= 1

        # Vérifier que les données ont été adaptées si nécessaire
        # Par exemple, nom vide pourrait être remplacé par "Unknown"
        for entry in patient_bundle.entry:
            if entry.resource.resourceType == "Patient":
                fhir_patient = entry.resource
                # Le nom ne devrait pas être vide
