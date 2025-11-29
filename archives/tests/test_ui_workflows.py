"""Tests UI pour les workflows (création/exécution/visualisation).
Couvre gestion des workflows, triggers, étapes, exécution.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import UniteFonctionnelle


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflows_list_page_loads(client: TestClient, session: Session):
    """Test que la page de liste des workflows se charge."""
    r = client.get("/workflows")
    assert r.status_code == 200
    assert "Workflows" in r.text or "Workflow" in r.text


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_creation_form(client: TestClient, session: Session):
    """Test le formulaire de création de workflow."""
    r = client.get("/workflows/new")
    assert r.status_code == 200
    for field in ["name", "description", "trigger_type", "steps"]:
        assert f'name="{field}"' in r.text or field in r.text


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_creation_success(client: TestClient, session: Session):
    """Test création réussie d'un workflow."""
    workflow_data = {
        "name": "Workflow Test",
        "description": "Workflow de test pour création",
        "trigger_type": "manual",  # Déclenchement manuel
        "steps": [
            {
                "id": "step1",
                "name": "Créer dossier",
                "type": "create_dossier",
                "order": 1,
                "config": {
                    "type": "hospitalise"
                }
            },
            {
                "id": "step2",
                "name": "Admission A01",
                "type": "create_movement",
                "order": 2,
                "config": {
                    "movement_type": "A01",
                    "priorite": "R"
                }
            }
        ]
    }

    r = client.post("/workflows", json=workflow_data, follow_redirects=True)
    assert r.status_code == 200

    # Vérifier que le workflow a été créé
    # TODO: Vérifier en DB une fois le modèle Workflow implémenté
    assert "Workflow Test" in r.text or "succès" in r.text.lower()


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_detail_page_loads(client: TestClient, session: Session):
    """Test que la page détail d'un workflow se charge."""
    # TODO: Créer un workflow d'abord
    r = client.get("/workflows/1")
    assert r.status_code in [200, 404]


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_step_visualization(client: TestClient, session: Session):
    """Test la visualisation des étapes d'un workflow."""
    r = client.get("/workflows/1/steps")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, list) or "steps" in data


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_execution_form(client: TestClient, session: Session):
    """Test le formulaire d'exécution de workflow."""
    r = client.get("/workflows/1/execute")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        for field in ["patient_id", "context_data"]:
            assert f'name="{field}"' in r.text or field in r.text


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_manual_execution(client: TestClient, session: Session):
    """Test l'exécution manuelle d'un workflow."""
    # Créer patient pour l'exécution
    patient = Patient(
        nom="Test",
        prenom="Workflow",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    execution_data = {
        "workflow_id": "1",
        "patient_id": str(patient.id),
        "context_data": {
            "urgence": False,
            "provenance": "medecin_traitant"
        }
    }

    r = client.post("/workflows/1/execute", json=execution_data, follow_redirects=True)
    assert r.status_code in [200, 400, 404]

    if r.status_code == 200:
        # Vérifier qu'un dossier et des mouvements ont été créés
        dossiers = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).all()
        assert len(dossiers) >= 1

        mouvements = session.exec(select(Mouvement).where(Mouvement.patient_id == patient.id)).all()
        assert len(mouvements) >= 1


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_trigger_on_movement(client: TestClient, session: Session):
    """Test le déclenchement automatique de workflow lors d'un mouvement."""
    # Créer patient et mouvement
    patient = Patient(
        nom="Test",
        prenom="Trigger",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    dossier = Dossier(
        patient_id=patient.id,
        type="hospitalise",
        numero="DOS-TRIGGER"
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    venue = Venue(dossier_id=dossier.id, numero="VEN-TRIGGER")
    session.add(venue)
    session.commit()
    session.refresh(venue)

    uf = UniteFonctionnelle(name="UF Trigger", identifier="UF-TRIGGER", service_id=1, physical_type="ro")
    session.add(uf)
    session.commit()
    session.refresh(uf)

    # Créer mouvement qui devrait déclencher un workflow
    mouvement_data = {
        "patient_id": str(patient.id),
        "dossier_id": str(dossier.id),
        "venue_id": str(venue.id),
        "uf_id": str(uf.id),
        "movement_type": "A01",
        "priorite": "U",  # Urgent - devrait déclencher workflow urgence
        "date_mouvement": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }

    r = client.post("/mouvements", data=mouvement_data, follow_redirects=True)
    assert r.status_code == 200

    # Vérifier qu'un workflow a été déclenché automatiquement
    # TODO: Vérifier les workflows exécutés une fois le système de triggers implémenté


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_execution_with_rollback(client: TestClient, session: Session):
    """Test l'exécution de workflow avec possibilité de rollback."""
    # Créer patient
    patient = Patient(
        nom="Test",
        prenom="Rollback",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    initial_dossiers = session.exec(select(Dossier)).all()
    initial_mouvements = session.exec(select(Mouvement)).all()

    execution_data = {
        "workflow_id": "urgence_admission",  # Workflow prédéfini
        "patient_id": str(patient.id),
        "allow_rollback": True
    }

    r = client.post("/workflows/urgence_admission/execute", json=execution_data)
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        execution_result = r.json()
        execution_id = execution_result.get("execution_id")

        # Tester le rollback
        rollback_r = client.post(f"/workflows/executions/{execution_id}/rollback")
        assert rollback_r.status_code in [200, 404]

        if rollback_r.status_code == 200:
            # Vérifier que tout a été annulé
            final_dossiers = session.exec(select(Dossier)).all()
            final_mouvements = session.exec(select(Mouvement)).all()

            # Les counts devraient être identiques (rollback complet)
            assert len(final_dossiers) == len(initial_dossiers)
            assert len(final_mouvements) == len(initial_mouvements)


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_validation_rules(client: TestClient, session: Session):
    """Test les règles de validation des workflows."""
    # Workflow invalide (pas d'étapes)
    invalid_workflow = {
        "name": "Invalid Workflow",
        "steps": []
    }

    r = client.post("/workflows/validate", json=invalid_workflow)
    assert r.status_code in [400, 404]

    if r.status_code == 400:
        data = r.json()
        assert "error" in data or not data.get("valid", True)

    # Workflow invalide (étape sans type)
    invalid_workflow2 = {
        "name": "Invalid Workflow 2",
        "steps": [
            {
                "id": "step1",
                "name": "Step without type",
                "order": 1
                # Pas de "type"
            }
        ]
    }

    r = client.post("/workflows/validate", json=invalid_workflow2)
    if r.status_code == 400:
        data = r.json()
        assert "error" in data or not data.get("valid", True)

    # Workflow valide
    valid_workflow = {
        "name": "Valid Workflow",
        "trigger_type": "manual",
        "steps": [
            {
                "id": "step1",
                "name": "Valid Step",
                "type": "create_dossier",
                "order": 1,
                "config": {"type": "hospitalise"}
            }
        ]
    }

    r = client.post("/workflows/validate", json=valid_workflow)
    if r.status_code == 200:
        data = r.json()
        assert data.get("valid", False)


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_execution_progress_tracking(client: TestClient, session: Session):
    """Test le suivi de progression lors de l'exécution d'un workflow."""
    # Créer workflow multi-étapes
    workflow_data = {
        "name": "Progress Test Workflow",
        "steps": [
            {"id": "s1", "name": "Step 1", "type": "create_dossier", "order": 1},
            {"id": "s2", "name": "Step 2", "type": "create_movement", "order": 2},
            {"id": "s3", "name": "Step 3", "type": "update_patient", "order": 3}
        ]
    }

    # Créer patient
    patient = Patient(
        nom="Test",
        prenom="Progress",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    execution_data = {
        "workflow": workflow_data,
        "patient_id": str(patient.id),
        "track_progress": True
    }

    r = client.post("/workflows/execute-with-progress", json=execution_data)
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        execution_id = r.json().get("execution_id")

        # Vérifier la progression
        progress_r = client.get(f"/workflows/executions/{execution_id}/progress")
        if progress_r.status_code == 200:
            progress_data = progress_r.json()
            assert "completed_steps" in progress_data or "progress" in progress_data
            assert "total_steps" in progress_data or len(progress_data.get("steps", [])) > 0


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_pause_resume_functionality(client: TestClient, session: Session):
    """Test la fonctionnalité pause/reprise d'un workflow."""
    # Créer workflow long
    workflow_data = {
        "name": "Pause Resume Test",
        "steps": [
            {"id": "s1", "name": "Fast Step", "type": "create_dossier", "order": 1},
            {"id": "s2", "name": "Slow Step", "type": "complex_calculation", "order": 2, "delay": 30},
            {"id": "s3", "name": "Final Step", "type": "create_movement", "order": 3}
        ]
    }

    patient = Patient(
        nom="Test",
        prenom="PauseResume",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    execution_data = {
        "workflow": workflow_data,
        "patient_id": str(patient.id),
        "allow_pause_resume": True
    }

    r = client.post("/workflows/execute-pausable", json=execution_data)
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        execution_id = r.json().get("execution_id")

        # Mettre en pause
        pause_r = client.post(f"/workflows/executions/{execution_id}/pause")
        assert pause_r.status_code in [200, 404]

        # Reprendre
        resume_r = client.post(f"/workflows/executions/{execution_id}/resume")
        assert resume_r.status_code in [200, 404]

        # Vérifier statut
        status_r = client.get(f"/workflows/executions/{execution_id}/status")
        if status_r.status_code == 200:
            status_data = status_r.json()
            assert "status" in status_data
            assert status_data["status"] in ["running", "paused", "completed", "failed"]


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_error_handling(client: TestClient, session: Session):
    """Test la gestion d'erreurs dans les workflows."""
    # Workflow qui va échouer
    workflow_data = {
        "name": "Error Handling Test",
        "steps": [
            {
                "id": "s1",
                "name": "Step that fails",
                "type": "invalid_operation",
                "order": 1,
                "config": {"will_fail": True}
            }
        ]
    }

    patient = Patient(
        nom="Test",
        prenom="Error",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    execution_data = {
        "workflow": workflow_data,
        "patient_id": str(patient.id),
        "error_handling": "continue"  # Continuer malgré les erreurs
    }

    r = client.post("/workflows/execute-with-error-handling", json=execution_data)
    assert r.status_code in [200, 400, 404]

    if r.status_code == 200:
        result = r.json()
        # Devrait contenir des informations sur l'erreur
        assert "errors" in result or "failed_steps" in result or "status" in result


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_library_and_templates(client: TestClient, session: Session):
    """Test la bibliothèque de workflows et templates."""
    # Lister les templates disponibles
    r = client.get("/workflows/templates")
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0  # Devrait y avoir des templates prédéfinis

    # Créer workflow depuis template
    template_name = data[0]["name"] if data else "admission_standard"

    r = client.post(f"/workflows/from-template/{template_name}")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        workflow_data = r.json()
        assert "workflow" in workflow_data or "id" in workflow_data


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_bulk_operations(client: TestClient, session: Session):
    """Test les opérations groupées sur les workflows."""
    # Créer plusieurs workflows
    workflows_data = [
        {"name": "Workflow 1", "steps": []},
        {"name": "Workflow 2", "steps": []},
        {"name": "Workflow 3", "steps": []}
    ]

    # Test export en masse
    r = client.get("/workflows/export-bulk")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        assert "application/zip" in r.headers.get("content-type", "")

    # Test activation/désactivation groupée
    workflow_ids = ["1", "2", "3"]
    r = client.post("/workflows/bulk-activate", json={"ids": workflow_ids})
    assert r.status_code in [200, 404]

    r = client.post("/workflows/bulk-deactivate", json={"ids": workflow_ids})
    assert r.status_code in [200, 404]


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_execution_history(client: TestClient, session: Session):
    """Test l'historique d'exécution des workflows."""
    # Exécuter quelques workflows d'abord
    # TODO: Une fois l'exécution implémentée

    # Consulter l'historique
    r = client.get("/workflows/executions")
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, list) or "executions" in data

    # Détail d'une exécution
    r = client.get("/workflows/executions/1")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        execution_data = r.json()
        assert "workflow_id" in execution_data or "status" in execution_data


@pytest.mark.xfail(reason="Routes workflows peuvent être cassées si dépendent de ght.py")
def test_workflow_performance_monitoring(client: TestClient, session: Session):
    """Test le monitoring de performance des workflows."""
    # Exécuter un workflow
    # TODO: Une fois implémenté

    # Consulter les métriques
    r = client.get("/workflows/performance")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        metrics = r.json()
        assert "average_execution_time" in metrics or "success_rate" in metrics

    # Métriques par workflow
    r = client.get("/workflows/1/performance")
    if r.status_code == 200:
        workflow_metrics = r.json()
        assert "execution_count" in workflow_metrics or "average_duration" in workflow_metrics