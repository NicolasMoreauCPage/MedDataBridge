# tests/ui/test_dossier_management_ui.py
"""
Tests d'interface utilisateur pour la gestion des dossiers
Tests de l'interface gestion dossiers et workflow médical
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.app import app
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import GHTContext


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

        assert response.status_code in [200, 302]

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
        assert response.status_code in [200, 302, 303]

        # Vérifier que le dossier a été créé
        dossiers = session.exec(
            select(Dossier).where(Dossier.patient_id == patient.id)
        ).all()

        assert len(dossiers) >= 1

    def test_dossier_detail_page_display(self, client, session: Session, sample_ght):
        """Test affichage de la page de détail de dossier"""
        # Créer patient et dossier
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier

        patient_data = PatientCreateSchema(
            family="DetailDossier",
            given="Test",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            patient_id=patient.id,
            admission_datetime="2025-01-01T10:00:00"
        )
        dossier = create_dossier(session=session, dossier_data=dossier_data, ght_context_id=sample_ght.id)

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
        from app.services.dossiers_service import DossierCreateSchema, create_dossier
        from app.services.venues_service import create_venue

        patient_data = PatientCreateSchema(
            family="TransitionTest",
            given="Patient",
            birth_date="1980-01-01"
        )
        patient = create_patient(session=session, patient_data=patient_data, ght_context_id=sample_ght.id)

        dossier_data = DossierCreateSchema(
            patient_id=patient.id,
            admission_datetime="2025-01-01T10:00:00"
        )
        dossier = create_dossier(session=session, dossier_data=dossier_data, ght_context_id=sample_ght.id)

        venue = create_venue(session=session, venue_data={
            "name": "Chambre 101",
            "venue_type": "HOSPITALISE"
        }, ght_context_id=sample_ght.id)

        # Tester l'ajout d'un mouvement (changement de venue)
        mouvement_data = {
            "venue_id": venue.id,
            "start_datetime": "2025-01-01T10:30:00",
            "mouvement_type": "ADMISSION"
        }

        response = client.post(f"/dossiers/{dossier.id}/mouvements", data=mouvement_data, follow_redirects=True)

        # Vérifier la réponse
        assert response.status_code in [200, 302, 303]

        # Vérifier que le mouvement a été créé
        mouvements = session.exec(
            select(Mouvement).where(Mouvement.dossier_id == dossier.id)
        ).all()

        assert len(mouvements) >= 1

    def test_dossier_medical_workflow_ui(self, client, session: Session, sample_ght):
        """Test workflow médical dans l'interface dossier"""
        # Créer les entités nécessaires
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier
        from app.services.venues_service import create_venue, create_chambre, create_lit

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="WorkflowTest", given="Patient", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier = create_dossier(session=session, dossier_data=DossierCreateSchema(
            patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
        ), ght_context_id=sample_ght.id)

        venue = create_venue(session=session, venue_data={
            "name": "Urgences", "venue_type": "URGENCE"
        }, ght_context_id=sample_ght.id)

        chambre = create_chambre(session=session, chambre_data={
            "name": "Box 1", "venue_id": venue.id, "is_generic": False, "max_occupancy": 1
        }, ght_context_id=sample_ght.id)

        lit = create_lit(session=session, lit_data={
            "name": "Lit 1", "chambre_id": chambre.id, "is_generic": False, "max_occupancy": 1
        }, ght_context_id=sample_ght.id)

        # Tester l'interface de workflow médical
        response = client.get(f"/dossiers/{dossier.id}/workflow")

        assert response.status_code in [200, 302]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'éléments de workflow
            assert "workflow" in content or "médical" in content or "venue" in content

    def test_dossier_search_and_filter_ui(self, client, session: Session, sample_ght):
        """Test recherche et filtrage de dossiers via UI"""
        # Créer plusieurs dossiers avec différents statuts
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier

        test_cases = [
            {"family": "Hospitalise", "status": "HOSPITALISE"},
            {"family": "Sorti", "status": "SORTI"},
            {"family": "Urgence", "status": "URGENCE"}
        ]

        for case in test_cases:
            patient = create_patient(session=session, patient_data=PatientCreateSchema(
                family=case["family"], given="Test", birth_date="1980-01-01"
            ), ght_context_id=sample_ght.id)

            dossier = create_dossier(session=session, dossier_data=DossierCreateSchema(
                patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
            ), ght_context_id=sample_ght.id)

            # Simuler différents statuts via mouvements
            if case["status"] == "HOSPITALISE":
                venue = session.exec(select(Venue).where(Venue.venue_type == "HOSPITALISE")).first()
                if not venue:
                    venue = create_venue(session=session, venue_data={
                        "name": "Médecine", "venue_type": "HOSPITALISE"
                    }, ght_context_id=sample_ght.id)

                mouvement = Mouvement(
                    dossier_id=dossier.id,
                    venue_id=venue.id,
                    mouvement_type="ADMISSION",
                    start_datetime="2025-01-01T10:00:00"
                )
                session.add(mouvement)
                session.commit()

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
        from app.services.dossiers_service import DossierCreateSchema, create_dossier
        from app.services.venues_service import create_venue

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="TimelineTest", given="Patient", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier = create_dossier(session=session, dossier_data=DossierCreateSchema(
            patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
        ), ght_context_id=sample_ght.id)

        # Créer plusieurs venues pour simuler des mouvements
        venues = []
        for i, venue_type in enumerate(["URGENCE", "HOSPITALISE", "SOINS_INTENSIFS"]):
            venue = create_venue(session=session, venue_data={
                "name": f"Venue {i+1}", "venue_type": venue_type
            }, ght_context_id=sample_ght.id)
            venues.append(venue)

        # Créer une séquence de mouvements
        mouvement_times = [
            "2025-01-01T10:00:00",  # Admission urgences
            "2025-01-01T12:00:00",  # Transfert hospitalisation
            "2025-01-01T18:00:00"   # Transfert soins intensifs
        ]

        for i, (venue, time) in enumerate(zip(venues, mouvement_times)):
            mouvement = Mouvement(
                dossier_id=dossier.id,
                venue_id=venue.id,
                mouvement_type="ADMISSION" if i == 0 else "TRANSFERT",
                start_datetime=time
            )
            session.add(mouvement)
        session.commit()

        # Tester l'affichage de la timeline
        response = client.get(f"/dossiers/{dossier.id}/timeline")

        assert response.status_code in [200, 302]

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence d'éléments de timeline
            assert "timeline" in content or "chronologie" in content or "mouvement" in content

    def test_dossier_export_functionality(self, client, session: Session, sample_ght):
        """Test fonctionnalité d'export de dossiers"""
        # Créer quelques dossiers
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier

        for i in range(3):
            patient = create_patient(session=session, patient_data=PatientCreateSchema(
                family="01d", given="Export", birth_date="1980-01-01"
            ), ght_context_id=sample_ght.id)

            create_dossier(session=session, dossier_data=DossierCreateSchema(
                patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
            ), ght_context_id=sample_ght.id)

        # Tester l'export
        response = client.get("/dossiers/export")

        assert response.status_code in [200, 302]

        # Tester l'export avec filtres
        response = client.post("/dossiers/export", data={
            "format": "pdf",
            "date_from": "2025-01-01",
            "date_to": "2025-12-31"
        }, follow_redirects=True)

        assert response.status_code in [200, 302]

    def test_dossier_bulk_operations_ui(self, client, session: Session, sample_ght):
        """Test opérations en masse sur les dossiers"""
        # Créer plusieurs dossiers
        from app.services.patients_service import PatientCreateSchema, create_patient
        from app.services.dossiers_service import DossierCreateSchema, create_dossier

        dossier_ids = []
        for i in range(3):
            patient = create_patient(session=session, patient_data=PatientCreateSchema(
                family="01d", given="Bulk", birth_date="1980-01-01"
            ), ght_context_id=sample_ght.id)

            dossier = create_dossier(session=session, dossier_data=DossierCreateSchema(
                patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
            ), ght_context_id=sample_ght.id)

            dossier_ids.append(str(dossier.id))

        # Tester les opérations en masse
        bulk_data = {
            "dossier_ids": dossier_ids,
            "action": "close",  # Fermeture en masse
            "reason": "Fin de séjour"
        }

        response = client.post("/dossiers/bulk", data=bulk_data, follow_redirects=True)

        # Vérifier la réponse
        assert response.status_code in [200, 302, 303]

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
        from app.services.dossiers_service import DossierCreateSchema, create_dossier

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="Accessibility", given="Test", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier = create_dossier(session=session, dossier_data=DossierCreateSchema(
            patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
        ), ght_context_id=sample_ght.id)

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
        from app.services.dossiers_service import DossierCreateSchema, create_dossier

        patient = create_patient(session=session, patient_data=PatientCreateSchema(
            family="Breadcrumb", given="Test", birth_date="1980-01-01"
        ), ght_context_id=sample_ght.id)

        dossier = create_dossier(session=session, dossier_data=DossierCreateSchema(
            patient_id=patient.id, admission_datetime="2025-01-01T10:00:00"
        ), ght_context_id=sample_ght.id)

        # Tester la navigation avec fil d'Ariane
        response = client.get(f"/dossiers/{dossier.id}")

        if response.status_code == 200:
            content = response.text.lower()
            # Vérifier la présence de navigation
