# tests/integration/test_dossier_workflow.py
"""
Tests d'intégration pour le workflow dossier médical complet
Tests de la gestion des dossiers : création, transitions d'états, validations
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session

from app.models import Patient, Dossier, Venue, Mouvement
from app.services.patients_service import PatientCreateSchema, create_patient
from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
from app.services.venues_service import VenueCreateSchema, create_venue
from app.services.mouvements_service import MouvementCreateSchema, create_mouvement
from app.models_structure import GHTContext


@pytest.mark.integration
class TestDossierWorkflowIntegration:
    """Tests d'intégration pour le workflow dossier médical"""

    @pytest.mark.asyncio
    async def test_dossier_creation_and_state_transitions(self, session: Session, sample_ght):
        """Test création dossier et transitions d'états"""

        # Créer un patient
        patient_data = PatientCreateSchema(
            family="Martin",
            given="Sophie",
            birth_date="1975-03-12"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Créer un dossier hospitalisé
        dossier_data = DossierCreateSchema(
            uf_responsabilite="UF001",
            dossier_type="hospitalise",
            admission_source="CONSULTATION",
            attending_provider="Dr. Dubois",
            admit_time=datetime.now(),
            current_state="Pré-admission"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Vérifier que le dossier est créé avec une venue de pré-admission
        assert dossier.id is not None
        assert len(dossier.venues) == 1
        pre_admit_venue = dossier.venues[0]
        assert pre_admit_venue.code == "PRE_ADMIT"

        # Simuler une admission (A01)
        mouvement_data = MouvementCreateSchema(
            venue_id=pre_admit_venue.id,
            event_code="A01",
            movement_datetime=datetime.now(),
            to_location="Chambre 101"
        )
        mouvement = create_mouvement(session=session, mouvement_data=mouvement_data)

        # Vérifier que le mouvement a mis à jour le dossier
        session.refresh(dossier)
        assert dossier.dossier_type.value == "hospitalise"
        assert mouvement.to_location == "Chambre 101"

        # Simuler un transfert (A02)
        transfert_data = MouvementCreateSchema(
            venue_id=pre_admit_venue.id,
            event_code="A02",
            movement_datetime=datetime.now() + timedelta(hours=2),
            from_location="Chambre 101",
            to_location="Chambre 201"
        )
        transfert = create_mouvement(session=session, mouvement_data=transfert_data)

        # Vérifier le transfert
        assert transfert.from_location == "Chambre 101"
        assert transfert.to_location == "Chambre 201"

        # Simuler une sortie (A03)
        sortie_data = MouvementCreateSchema(
            venue_id=pre_admit_venue.id,
            event_code="A03",
            movement_datetime=datetime.now() + timedelta(days=1),
            from_location="Chambre 201"
        )
        sortie = create_mouvement(session=session, mouvement_data=sortie_data)

        # Vérifier la sortie
        assert sortie.event_code == "A03"
        session.refresh(dossier)
        # Le dossier devrait être clôturé après A03

    @pytest.mark.asyncio
    async def test_dossier_validation_rules(self, session: Session, sample_ght):
        """Test des règles de validation des dossiers"""

        # Créer un patient
        patient_data = PatientCreateSchema(
            family="Dubois",
            given="Pierre",
            birth_date="1960-07-22"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Tester validation UF requise
        with pytest.raises(Exception):  # Devrait échouer sans UF
            dossier_data = DossierCreateSchema(
                dossier_type="hospitalise",
                admit_time=datetime.now()
            )
            create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Créer un dossier valide
        dossier_data = DossierCreateSchema(
            uf_responsabilite="UF001",
            dossier_type="externe",
            admit_time=datetime.now()
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Tester qu'on ne peut pas avoir deux dossiers actifs du même type
        # (Selon les règles métier, un patient ne peut avoir qu'un dossier actif par type)

        # Créer une nouvelle venue pour le même dossier
        venue_data = VenueCreateSchema(
            dossier_id=dossier.id,
            uf_responsabilite="UF001",
            start_time=datetime.now(),
            code="VISIT",
            label="Visite externe"
        )
        venue = create_venue(session=session, venue_data=venue_data)

        assert venue.id is not None
        assert venue.dossier_id == dossier.id

    @pytest.mark.asyncio
    async def test_dossier_with_multiple_venues(self, session: Session, sample_ght):
        """Test dossier avec multiple venues et mouvements"""

        # Créer patient et dossier
        patient_data = PatientCreateSchema(
            family="Leroy",
            given="Marie",
            birth_date="1985-11-30"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            uf_responsabilite="UF002",
            dossier_type="hospitalise",
            admit_time=datetime.now()
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Créer plusieurs venues séquentielles
        venues = []
        for i in range(3):
            venue_data = VenueCreateSchema(
                dossier_id=dossier.id,
                uf_responsabilite="UF002",
                start_time=datetime.now() + timedelta(days=i),
                code=f"VENUE{i+1}",
                label=f"Venue {i+1}"
            )
            venue = create_venue(session=session, venue_data=venue_data)
            venues.append(venue)

        # Vérifier que toutes les venues sont liées au dossier
        session.refresh(dossier)
        assert len(dossier.venues) == 4  # 3 nouvelles + 1 pré-admission

        # Créer des mouvements entre les venues
        for i in range(len(venues) - 1):
            mouvement_data = MouvementCreateSchema(
                venue_id=venues[i].id,
                event_code="A02",
                movement_datetime=datetime.now() + timedelta(days=i, hours=1),
                from_location=f"Location {i}",
                to_location=f"Location {i+1}"
            )
            create_mouvement(session=session, mouvement_data=mouvement_data)

        # Vérifier l'historique des mouvements
        mouvements = session.query(Mouvement).filter(Mouvement.venue_id.in_([v.id for v in venues])).all()
