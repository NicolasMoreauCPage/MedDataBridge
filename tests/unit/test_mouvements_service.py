"""
Tests unitaires pour les services mouvements (sans TestClient)
"""

from datetime import datetime
from sqlmodel import Session
from app.models import Dossier, Patient, Venue
from app.services.mouvements_service import MouvementCreateSchema, create_mouvement


class TestMouvementsService:
    """Tests unitaires pour le service mouvements"""

    def test_create_mouvement_success(self, session: Session):
        """Test création mouvement réussie"""
        # Créer des données de test
        patient = Patient(family="Mouvement", given="Test")
        session.add(patient)
        session.flush()
        dossier = Dossier(
            patient_id=patient.id,
            admit_time=datetime.now(),
            discharge_time=None
        )
        session.add(dossier)
        session.commit()  # Commit d'abord le dossier

        venue = Venue(
            dossier_id=dossier.id,  # Utiliser l'ID du dossier créé
            venue_seq=1,
            admit_time=datetime.now(),
            start_time=datetime.now()  # Champ requis
        )
        session.add(venue)
        session.commit()  # Puis commit la venue

        mouvement_data = MouvementCreateSchema(
            venue_id=venue.id,
            when=datetime.now(),
            trigger_event="A01",
            location="CHAMBRE_101",
            status="active"
        )

        mouvement = create_mouvement(session=session, mouvement_data=mouvement_data)

        assert mouvement.id is not None
        assert mouvement.trigger_event == "A01"
        assert mouvement.location == "CHAMBRE_101"
        assert mouvement.status == "active"
        assert mouvement.mouvement_seq is not None

    def test_create_mouvement_minimal(self, session: Session):
        """Test création mouvement avec données minimales"""
        # Créer des données de test
        patient = Patient(family="Mouvement", given="Minimal")
        session.add(patient)
        session.flush()
        dossier = Dossier(
            patient_id=patient.id,
            admit_time=datetime.now()
        )
        session.add(dossier)
        session.commit()  # Commit d'abord le dossier

        venue = Venue(
            dossier_id=dossier.id,  # Utiliser l'ID du dossier créé
            venue_seq=2,
            admit_time=datetime.now(),
            start_time=datetime.now()  # Champ requis
        )
        session.add(venue)
        session.commit()  # Puis commit la venue

        mouvement_data = MouvementCreateSchema(
            venue_id=venue.id,
            when=datetime.now(),
            trigger_event="A02"
        )

        mouvement = create_mouvement(session=session, mouvement_data=mouvement_data)

        assert mouvement.id is not None
        assert mouvement.trigger_event == "A02"
        assert mouvement.mouvement_seq is not None
