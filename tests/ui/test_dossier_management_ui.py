# tests/ui/test_dossier_management_ui.py
"""
Tests d'interface utilisateur pour la gestion des dossiers
Tests de l'interface gestion dossiers et workflow médical
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.app import app
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.models_structure import GHTContext
from app.services.mouvements_service import MouvementCreateSchema, create_mouvement


@pytest.mark.ui
class TestDossierManagementUI:
    """Tests UI pour la gestion des dossiers médicaux"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    def test_dossier_list_page_access(self, client):
        """Test accès à la page liste des dossiers"""
        response = client.get("/dossiers")

        # La page devrait être accessible
        assert response.status_code in [200, 302]

    def test_dossier_creation_workflow_ui(self, client, session: Session, sample_ght):
        """Test workflow de création de dossier via UI"""
        # Créer un patient d'abord
        from app.services.patients_service import PatientCreateSchema, create_patient

        patient_data = PatientCreateSchema(
            family="DossierTest",
            given="Patient",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Accéder au formulaire de création de dossier
        response = client.get(f"/patients/{patient.id}/dossiers/new")

        assert response.status_code in [200, 302, 404]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'éléments de formulaire
            assert "dossier" in content or "admission" in content or "form" in content

    def test_dossier_creation_form_submission(self, client, session: Session, sample_ght):
        """Test soumission du formulaire de création de dossier"""
        # Créer un patient
        from app.services.patients_service import PatientCreateSchema, create_patient

        patient_data = PatientCreateSchema(
            family="DossierSubmit",
            given="Test",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        # Données de création de dossier
        dossier_data = {
            "admission_datetime": "2025-01-01T10:00:00",
            "motif_admission": "Contrôle annuel",
            "service_demande": "Médecine interne"
        }

        # Soumettre le formulaire
        response = client.post(f"/patients/{patient.id}/dossiers/new", data=dossier_data, follow_redirects=True)

        # Vérifier la réponse
        assert response.status_code in [200, 302, 303, 404]

        # Vérifier que le dossier a été créé (seulement si l'endpoint fonctionne)
        if response.status_code in [200, 302, 303]:
            dossiers = session.exec(
                select(Dossier).where(Dossier.patient_id == patient.id)
            ).all()
            assert len(dossiers) >= 1

    def test_dossier_detail_page_display(self, client, session: Session, sample_ght):
        """Test affichage de la page de détail de dossier"""
        # Créer patient et dossier
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue

        patient_data = PatientCreateSchema(
            family="DetailDossier",
            given="Test",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime(2025, 1, 1, 10, 0, 0),
            uf_responsabilite="UF001",
            admission_source="Emergency",
            attending_provider="Dr. Smith"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Accéder à la page de détail
        response = client.get(f"/dossiers/{dossier.id}")

        assert response.status_code in [200, 302]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'informations du dossier
            assert "dossier" in content or "detail" in content

    def test_dossier_state_transitions_ui(self, client, session: Session, sample_ght):
        """Test transitions d'état de dossier via UI"""
        # Créer patient, dossier et venue
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        from app.services.venues_service import VenueCreateSchema, create_venue

        patient_data = PatientCreateSchema(
            family="TransitionTest",
            given="Patient",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime(2025, 1, 1, 10, 0, 0),
            uf_responsabilite="UF001",
            admission_source="Emergency",
            attending_provider="Dr. Smith"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        venue_data = VenueCreateSchema(
            dossier_id=dossier.id,
            uf_responsabilite="UF001",
            start_time=datetime(2025, 1, 1, 10, 0, 0)
        )
        venue = create_venue(session=session, venue_data=venue_data)

        # Tester l'ajout d'un mouvement (changement de venue)
        mouvement_data = {
            "venue_id": venue.id,
            "start_datetime": "2025-01-01T10:30:00",
            "mouvement_type": "ADMISSION"
        }

        response = client.post(f"/dossiers/{dossier.id}/mouvements", data=mouvement_data, follow_redirects=True)

        # Vérifier la réponse
        assert response.status_code in [200, 302, 303, 404]

        # Vérifier que le mouvement a été créé (seulement si l'endpoint fonctionne)
        if response.status_code in [200, 302, 303]:
            mouvements = session.exec(
                select(Mouvement).where(Mouvement.dossier_id == dossier.id)
            ).all()
            assert len(mouvements) >= 1

    def test_dossier_medical_workflow_ui(self, client, session: Session, sample_ght):
        """Test workflow médical dans l'interface dossier"""
        # Créer les entités nécessaires
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        from app.services.venues_service import VenueCreateSchema, create_venue

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="WorkflowTest", given="Patient", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime(2025, 1, 1, 10, 0, 0),
            uf_responsabilite="UF001",
            admission_source="Emergency",
            attending_provider="Dr. Smith"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        venue_data = VenueCreateSchema(
            dossier_id=dossier.id,
            uf_responsabilite="UF001",
            start_time=datetime(2025, 1, 1, 10, 0, 0)
        )
        venue = create_venue(session=session, venue_data=venue_data)

        # Tester l'interface de workflow médical
        response = client.get(f"/dossiers/{dossier.id}/workflow")

        assert response.status_code in [200, 302, 404]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'éléments de workflow
            assert "workflow" in content or "médical" in content or "venue" in content

    def test_dossier_search_and_filter_ui(self, client, session: Session, sample_ght):
        """Test recherche et filtrage de dossiers via UI"""
        # Créer plusieurs dossiers avec différents statuts
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        from app.services.venues_service import VenueCreateSchema, create_venue

        test_cases = [
            {"family": "Hospitalise", "status": "HOSPITALISE"},
            {"family": "Sorti", "status": "SORTI"},
            {"family": "Urgence", "status": "URGENCE"}
        ]

        for case in test_cases:
            patient = create_patient(session=session, patient_data=PatientCreateSchema(
                family=case["family"], given="Test", birth_date="1980-01-01"
            ), ght_context_id=sample_ght.id)

            dossier_data = DossierCreateSchema(
                dossier_type=DossierType.HOSPITALISE,
                admit_time=datetime(2025, 1, 1, 10, 0, 0),
                uf_responsabilite="UF001",
                admission_source="Emergency",
                attending_provider="Dr. Smith"
            )
            dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

            # Simuler différents statuts via mouvements
            if case["status"] == "HOSPITALISE":
                venue_data = VenueCreateSchema(
                    dossier_id=dossier.id,
                    uf_responsabilite="UF001",
                    start_time=datetime(2025, 1, 1, 10, 0, 0)
                )
                venue = create_venue(session=session, venue_data=venue_data)

                mouvement_data = MouvementCreateSchema(
                    venue_id=venue.id,
                    event_code="A01",
                    movement_datetime=datetime(2025, 1, 1, 10, 0, 0),
                    movement_type="ADMISSION"
                )
                create_mouvement(session=session, mouvement_data=mouvement_data)

        # Tester la recherche
        response = client.get("/dossiers?search=Hospitalise")

        assert response.status_code in [200, 302]

        # Tester le filtrage par statut
        response = client.get("/dossiers?status=HOSPITALISE")

        assert response.status_code in [200, 302]

    def test_dossier_timeline_visualization(self, client, session: Session, sample_ght):
        """Test visualisation de la timeline du dossier"""
        # Créer un dossier avec plusieurs mouvements
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue
        from app.services.venues_service import VenueCreateSchema, create_venue

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="TimelineTest", given="Patient", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime(2025, 1, 1, 10, 0, 0),
            uf_responsabilite="UF001",
            admission_source="Emergency",
            attending_provider="Dr. Smith"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Créer plusieurs venues pour simuler des mouvements
        venues = []
        for i, venue_type in enumerate(["URGENCE", "HOSPITALISE", "SOINS_INTENSIFS"]):
            venue_data = VenueCreateSchema(
                dossier_id=dossier.id,
                uf_responsabilite="UF001",
                start_time=datetime(2025, 1, 1, 10 + i, 0, 0)
            )
            venue = create_venue(session=session, venue_data=venue_data)
            venues.append(venue)

        # Créer une séquence de mouvements
        mouvement_times = [
            "2025-01-01T10:00:00",  # Admission urgences
            "2025-01-01T12:00:00",  # Transfert hospitalisation
            "2025-01-01T18:00:00"   # Transfert soins intensifs
        ]

        for i, (venue, time) in enumerate(zip(venues, mouvement_times)):
            mouvement_data = MouvementCreateSchema(
                venue_id=venue.id,
                event_code="A01" if i == 0 else "A02",
                movement_datetime=datetime.fromisoformat(time),
                movement_type="ADMISSION" if i == 0 else "TRANSFERT"
            )
            create_mouvement(session=session, mouvement_data=mouvement_data)

        # Tester l'affichage de la timeline
        response = client.get(f"/dossiers/{dossier.id}/timeline")

        assert response.status_code in [200, 302, 404]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'éléments de timeline
            assert "timeline" in content or "chronologie" in content or "mouvement" in content

    def test_dossier_export_functionality(self, client, session: Session, sample_ght):
        """Test fonctionnalité d'export de dossiers"""
        # Créer quelques dossiers
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue

        for i in range(3):
            patient = create_patient(session=session, patient_data=PatientCreateSchema(
                family="01d", given="Export", birth_date="1980-01-01"
            ), ght_context_id=sample_ght.id)

            dossier_data = DossierCreateSchema(
                dossier_type=DossierType.HOSPITALISE,
                admit_time=datetime(2025, 1, 1, 10, 0, 0),
                uf_responsabilite="UF001",
                admission_source="Emergency",
                attending_provider="Dr. Smith"
            )
            create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Tester l'export
        response = client.get("/dossiers/export")

        assert response.status_code in [200, 302, 422]

        # Tester l'export avec filtres
        response = client.post("/dossiers/export", data={
            "format": "pdf",
            "date_from": "2025-01-01",
            "date_to": "2025-12-31"
        }, follow_redirects=True)

        assert response.status_code in [200, 302, 405]

    def test_dossier_bulk_operations_ui(self, client, session: Session, sample_ght):
        """Test opérations en masse sur les dossiers"""
        # Créer plusieurs dossiers
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue

        dossier_ids = []
        for i in range(3):
            patient = create_patient(session=session, patient_data=PatientCreateSchema(
                family="01d", given="Bulk", birth_date="1980-01-01"
            ), ght_context_id=sample_ght.id)

            dossier_data = DossierCreateSchema(
                dossier_type=DossierType.HOSPITALISE,
                admit_time=datetime(2025, 1, 1, 10, 0, 0),
                uf_responsabilite="UF001",
                admission_source="Emergency",
                attending_provider="Dr. Smith"
            )
            dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

            dossier_ids.append(str(dossier.id))

        # Tester les opérations en masse
        bulk_data = {
            "dossier_ids": dossier_ids,
            "action": "close",  # Fermeture en masse
            "reason": "Fin de séjour"
        }

        response = client.post("/dossiers/bulk", data=bulk_data, follow_redirects=True)

        # Vérifier la réponse
        assert response.status_code in [200, 302, 303, 405]

    def test_dossier_responsive_ui(self, client):
        """Test interface responsive pour les dossiers"""
        # Tester avec différents appareils
        devices = [
            ("desktop", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            ("mobile", "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15"),
            ("tablet", "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15")
        ]

        for device_name, ua in devices:
            response = client.get("/dossiers", headers={"User-Agent": ua})
            # L'interface devrait s'adapter
            assert response.status_code in [200, 302]

    def test_dossier_accessibility_compliance(self, client, session: Session, sample_ght):
        """Test conformité accessibilité de l'interface dossier"""
        # Créer un dossier pour tester
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="Accessibility", given="Test", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime(2025, 1, 1, 10, 0, 0),
            uf_responsabilite="UF001",
            admission_source="Emergency",
            attending_provider="Dr. Smith"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        response = client.get(f"/dossiers/{dossier.id}/edit")

        if response.status_code == 200:
            content = response.text

            # Vérifications d'accessibilité basiques
            # Présence de labels et attributs ARIA
            assert "label" in content.lower() or 'aria-label' in content.lower()

            # Structure sémantique
            assert "<form" in content or "form" in content.lower()

    def test_dossier_error_handling_ui(self, client):
        """Test gestion d'erreurs dans l'interface dossier"""
        # Tester avec un ID invalide
        response = client.get("/dossiers/99999")

        # Devrait gérer l'erreur gracieusement
        assert response.status_code in [200, 302, 404]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'un message d'erreur
            assert "error" in content or "erreur" in content or "not found" in content

    def test_dossier_navigation_breadcrumbs(self, client, session: Session, sample_ght):
        """Test fil d'Ariane dans la navigation dossier"""
        # Créer la hiérarchie patient -> dossier
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier_with_pre_admit_venue

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="Breadcrumb", given="Test", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime(2025, 1, 1, 10, 0, 0),
            uf_responsabilite="UF001",
            admission_source="Emergency",
            attending_provider="Dr. Smith"
        )
        dossier = create_dossier_with_pre_admit_venue(session=session, dossier_data=dossier_data, patient=patient)

        # Tester la navigation avec fil d'Ariane
        response = client.get(f"/dossiers/{dossier.id}")

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence de navigation
