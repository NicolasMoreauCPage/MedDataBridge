# tests/integration/test_patient_workflow.py
"""
Tests d'intégration pour le workflow patient complet
Tests du workflow : création patient → création dossier → ajout actes → export FHIR
"""

import pytest
from datetime import datetime, date
from sqlmodel import Session

from app.models import Patient, Dossier, UCDAct, LPPAct
from app.services.patients_service import PatientCreateSchema, create_patient
from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
from app.services.ucd_service import UCDService
from app.services.lpp_service import LPPService
from app.schemas.ucd import UCDActCreate
from app.schemas.lpp import LPPActCreate
from app.services.fhir_export_service import FHIRExportService
from app.models_structure import EntiteJuridique


@pytest.mark.integration
class TestPatientWorkflowIntegration:
    """Tests d'intégration pour le workflow patient complet"""

    @pytest.mark.asyncio
    async def test_complete_patient_workflow(self, session: Session, sample_ght):
        """Test workflow complet : patient → dossier → actes → export FHIR"""

        # Étape 1: Création du patient
        patient_data = PatientCreateSchema(
            family="Dupont",
            given="Jean",
            birth_date="1980-01-15",
            gender="M"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)
        assert patient.id is not None
        assert patient.family == "Dupont"
        assert patient.given == "Jean"
        assert patient.birth_date == date(1980, 1, 15)

        # Étape 2: Création du dossier médical
        dossier_data = DossierCreateSchema(
            uf_responsabilite="UF001",
            dossier_type="hospitalise",
            admission_source="URGENCES",
            attending_provider="Dr. Martin",
            admit_time=datetime.now(),
            current_state="Actif"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)
        assert dossier.id is not None
        assert dossier.patient_id == patient.id
        assert dossier.dossier_type.value == "hospitalise"
        assert dossier.uf_responsabilite == "UF001"

        # Étape 3: Ajout d'actes UCD
        ucd_service = UCDService(session)
        ucd_act_data = UCDActCreate(
            dossier_id=dossier.id,
            code_cip="3400935001325",
            designation="PARACETAMOL 500MG CPR",
            quantite=10,
            prix_unitaire=0.50,
            montant_total=5.00,
            execute_date=datetime.now(),
            prestataire_id="PREST001",
            commentaire="Test UCD act"
        )
        ucd_act = await ucd_service.create_act(ucd_act_data)
        assert ucd_act.id is not None
        assert ucd_act.dossier_id == dossier.id
        assert ucd_act.code_cip == "3400935001325"
        assert ucd_act.quantite == 10

        # Étape 4: Ajout d'actes LPP
        lpp_service = LPPService(session)
        lpp_act_data = LPPActCreate(
            dossier_id=dossier.id,
            code_lpp="HLPP001",
            designation="Consultation cardiologie",
            quantite=1,
            prix_unitaire=50.00,
            montant_total=50.00,
            execute_date=datetime.now(),
            prestataire_id="PREST002",
            commentaire="Test LPP act"
        )
        lpp_act = await lpp_service.create_act(lpp_act_data)
        assert lpp_act.id is not None
        assert lpp_act.dossier_id == dossier.id
        assert lpp_act.code_lpp == "HLPP001"
        assert lpp_act.quantite == 1

        # Étape 5: Export FHIR des patients
        # Créer une EJ fictive pour le test
        ej = EntiteJuridique(
            id=1,
            name="Test EJ",
            ght_context_id=sample_ght.id
        )
        session.add(ej)
        session.commit()

        fhir_service = FHIRExportService(session, "http://localhost:8000/fhir")
        patient_bundle = fhir_service.export_patients(ej)

        # Vérifications de l'export FHIR
        assert patient_bundle is not None
        assert len(patient_bundle.entry) >= 1  # Au moins notre patient

        # Trouver notre patient dans le bundle
        patient_resource = None
        for entry in patient_bundle.entry:
            if entry.resource.resourceType == "Patient":
                if hasattr(entry.resource, 'identifier'):
                    for identifier in entry.resource.identifier:
                        if identifier.value == patient.identifier:
                            patient_resource = entry.resource
                            break
            if patient_resource:
                break

        assert patient_resource is not None, "Patient non trouvé dans l'export FHIR"
        assert patient_resource.name[0].family == "Dupont"
        assert patient_resource.name[0].given[0] == "Jean"
        assert patient_resource.birthDate == "1980-01-15"

        # Vérifier que les actes sont présents (via extensions ou ressources liées)
        # Note: L'implémentation exacte dépend de la structure FHIR choisie

    @pytest.mark.asyncio
    async def test_patient_workflow_with_multiple_dossiers(self, session: Session, sample_ght):
        """Test patient avec multiple dossiers"""

        # Créer un patient
        patient_data = PatientCreateSchema(
            family="Martin",
            given="Marie",
            birth_date="1990-05-20"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Créer deux dossiers
        dossier1_data = DossierCreateSchema(
            uf_responsabilite="UF001",
            dossier_type="hospitalise",
            admit_time=datetime.now()
        )
        dossier1 = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier1_data, patient=patient)

        dossier2_data = DossierCreateSchema(
            uf_responsabilite="UF002",
            dossier_type="externe",
            admit_time=datetime.now()
        )
        dossier2 = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier2_data, patient=patient)

        # Vérifier que les deux dossiers sont liés au patient
        assert dossier1.patient_id == patient.id
        assert dossier2.patient_id == patient.id
        assert dossier1.id != dossier2.id

        # Ajouter des actes à chaque dossier
        ucd_service = UCDService(session)

        ucd_act1 = UCDActCreate(
            dossier_id=dossier1.id,
            code_cip="3400935001325",
            designation="Médicament 1",
            quantite=5,
            prix_unitaire=1.00,
            montant_total=5.00,
            execute_date=datetime.now()
        )
        await ucd_service.create_act(ucd_act1)

        ucd_act2 = UCDActCreate(
            dossier_id=dossier2.id,
            code_cip="3400935001326",
            designation="Médicament 2",
            quantite=3,
            prix_unitaire=2.00,
            montant_total=6.00,
            execute_date=datetime.now()
        )
        await ucd_service.create_act(ucd_act2)

        # Vérifier que les actes sont bien séparés par dossier
        acts_dossier1 = await ucd_service.get_acts_by_dossier(dossier1.id)
        acts_dossier2 = await ucd_service.get_acts_by_dossier(dossier2.id)

        assert len(acts_dossier1) == 1
        assert len(acts_dossier2) == 1
        assert acts_dossier1[0].code_cip == "3400935001325"
        assert acts_dossier2[0].code_cip == "3400935001326"
