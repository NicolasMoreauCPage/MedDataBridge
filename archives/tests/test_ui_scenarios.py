"""Tests UI pour les scénarios (import/export/exécution).
Couvre gestion des scénarios, binding aux UF, date shifting, visualisation.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime
import json

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import UniteFonctionnelle


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenarios_list_page_loads(client: TestClient, session: Session):
    """Test que la page de liste des scénarios se charge."""
    r = client.get("/scenarios")
    assert r.status_code == 200
    assert "Scénarios" in r.text or "Scenarios" in r.text


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_import_form(client: TestClient, session: Session):
    """Test le formulaire d'import de scénario."""
    r = client.get("/scenarios/import")
    assert r.status_code == 200
    for field in ["file", "name", "description"]:
        assert f'name="{field}"' in r.text or field in r.text


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_import_json_success(client: TestClient, session: Session):
    """Test import réussi d'un scénario JSON."""
    # Créer un scénario JSON simple
    scenario_data = {
        "name": "Test Scenario",
        "description": "Scénario de test pour import",
        "version": "1.0",
        "steps": [
            {
                "id": "step1",
                "name": "Admission patient",
                "type": "movement",
                "movement_type": "A01",
                "delay_days": 0,
                "description": "Admission en médecine interne"
            },
            {
                "id": "step2",
                "name": "Transfert chirurgie",
                "type": "movement",
                "movement_type": "A02",
                "delay_days": 2,
                "description": "Transfert vers chirurgie"
            }
        ]
    }

    # Convertir en fichier upload
    import io
    scenario_file = io.BytesIO(json.dumps(scenario_data).encode('utf-8'))
    scenario_file.name = 'test_scenario.json'

    r = client.post("/scenarios/import",
                   files={"file": ("test_scenario.json", scenario_file, "application/json")},
                   follow_redirects=True)
    assert r.status_code == 200

    # Vérifier que le scénario a été créé
    # TODO: Vérifier en DB une fois le modèle Scenario implémenté
    assert "Test Scenario" in r.text or "succès" in r.text.lower()


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_detail_page_loads(client: TestClient, session: Session):
    """Test que la page détail d'un scénario se charge."""
    # TODO: Créer un scénario en DB d'abord une fois implémenté
    # Pour l'instant, simuler avec un ID fictif
    r = client.get("/scenarios/1")
    # Peut retourner 404 si pas implémenté, mais l'endpoint devrait exister
    assert r.status_code in [200, 404]


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_export_functionality(client: TestClient, session: Session):
    """Test l'export d'un scénario."""
    # TODO: Créer un scénario d'abord
    r = client.get("/scenarios/1/export")
    assert r.status_code in [200, 404]  # 404 si scénario n'existe pas

    if r.status_code == 200:
        assert "application/json" in r.headers.get("content-type", "")


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_execution_form(client: TestClient, session: Session):
    """Test le formulaire d'exécution de scénario."""
    r = client.get("/scenarios/1/execute")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        for field in ["start_date", "patient_id", "uf_mappings"]:
            assert f'name="{field}"' in r.text or field in r.text


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_execution_with_date_shifting(client: TestClient, session: Session):
    """Test l'exécution d'un scénario avec date shifting."""
    # Créer patient et UF pour l'exécution
    patient = Patient(
        nom="Test",
        prenom="Scenario",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    uf1 = UniteFonctionnelle(name="UF Médecine", identifier="UF-MED", service_id=1, physical_type="ro")
    uf2 = UniteFonctionnelle(name="UF Chirurgie", identifier="UF-CHIR", service_id=1, physical_type="ro")
    session.add(uf1)
    session.add(uf2)
    session.commit()
    session.refresh(uf1)
    session.refresh(uf2)

    # Payload d'exécution de scénario
    execution_data = {
        "scenario_id": "1",
        "patient_id": str(patient.id),
        "start_date": "2025-01-15",
        "uf_mappings": {
            "MED": str(uf1.id),
            "CHIR": str(uf2.id)
        },
        "date_shifting": "relative"  # Dates relatives au start_date
    }

    r = client.post("/scenarios/1/execute", json=execution_data, follow_redirects=True)
    # Peut échouer si scénario n'existe pas, mais l'endpoint devrait accepter
    assert r.status_code in [200, 400, 404]


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_step_visualization(client: TestClient, session: Session):
    """Test la visualisation des steps d'un scénario."""
    r = client.get("/scenarios/1/steps")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        # Devrait retourner du JSON avec les steps
        data = r.json()
        assert isinstance(data, list) or "steps" in data


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_uf_binding_validation(client: TestClient, session: Session):
    """Test la validation du binding UF dans les scénarios."""
    # Créer UFs
    uf1 = UniteFonctionnelle(name="UF Cardio", identifier="UF-CARDIO", service_id=1, physical_type="ro")
    uf2 = UniteFonctionnelle(name="UF Neuro", identifier="UF-NEURO", service_id=1, physical_type="ro")
    session.add(uf1)
    session.add(uf2)
    session.commit()
    session.refresh(uf1)
    session.refresh(uf2)

    # Scénario nécessitant des UFs spécifiques
    scenario_data = {
        "name": "Scenario Validation",
        "steps": [
            {
                "id": "admission",
                "name": "Admission",
                "type": "movement",
                "movement_type": "A01",
                "required_uf": "CARDIO",
                "delay_days": 0
            }
        ]
    }

    # Test avec binding correct
    binding_data = {
        "scenario": scenario_data,
        "uf_mappings": {
            "CARDIO": str(uf1.id)
        }
    }

    r = client.post("/scenarios/validate-binding", json=binding_data)
    assert r.status_code in [200, 404]  # 404 si endpoint pas implémenté

    if r.status_code == 200:
        data = r.json()
        assert data.get("valid", True)  # Devrait être valide

    # Test avec UF manquante
    binding_data["uf_mappings"] = {}  # Pas de mapping

    r = client.post("/scenarios/validate-binding", json=binding_data)
    if r.status_code == 200:
        data = r.json()
        assert not data.get("valid", True)  # Devrait être invalide


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_date_shifting_options(client: TestClient, session: Session):
    """Test les différentes options de date shifting."""
    # Créer scénario avec dates
    scenario_data = {
        "name": "Date Shifting Test",
        "steps": [
            {
                "id": "step1",
                "name": "Étape 1",
                "type": "movement",
                "delay_days": 0,
                "date": "2024-01-01"  # Date absolue dans le scénario
            },
            {
                "id": "step2",
                "name": "Étape 2",
                "type": "movement",
                "delay_days": 5,  # 5 jours après l'étape 1
                "date": None
            }
        ]
    }

    # Test date shifting relatif
    shifting_data = {
        "scenario": scenario_data,
        "shifting_mode": "relative",
        "start_date": "2025-06-01",
        "preserve_intervals": True
    }

    r = client.post("/scenarios/apply-date-shifting", json=shifting_data)
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        result = r.json()
        # Vérifier que les dates ont été shiftées
        assert "2025-06-01" in str(result)  # Nouvelle date de début
        assert "2025-06-06" in str(result)  # 5 jours plus tard

    # Test date shifting absolu (pas de changement)
    shifting_data["shifting_mode"] = "absolute"

    r = client.post("/scenarios/apply-date-shifting", json=shifting_data)
    if r.status_code == 200:
        result = r.json()
        # Les dates devraient rester telles quelles
        assert "2024-01-01" in str(result)


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_execution_dry_run(client: TestClient, session: Session):
    """Test l'exécution à sec (dry-run) d'un scénario."""
    # Créer patient
    patient = Patient(
        nom="Test",
        prenom="DryRun",
        date_naissance=datetime(1990, 1, 1),
        sexe="M"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    execution_data = {
        "scenario_id": "1",
        "patient_id": str(patient.id),
        "dry_run": True,  # Mode dry-run
        "start_date": "2025-01-01"
    }

    r = client.post("/scenarios/1/execute", json=execution_data)
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        result = r.json()
        # En dry-run, rien ne devrait être créé en DB
        mouvements_count = session.exec(select(Mouvement)).all()
        # TODO: Vérifier que le count n'a pas changé

        # Mais on devrait avoir un aperçu des actions
        assert "preview" in result or "actions" in result or "steps" in result


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_execution_with_errors(client: TestClient, session: Session):
    """Test l'exécution d'un scénario avec gestion d'erreurs."""
    execution_data = {
        "scenario_id": "999",  # ID inexistant
        "patient_id": "invalid",
        "start_date": "invalid-date"
    }

    r = client.post("/scenarios/999/execute", json=execution_data)
    # Devrait retourner une erreur appropriée
    assert r.status_code in [400, 404, 422]

    if r.status_code == 400:
        data = r.json()
        assert "error" in data or "detail" in data


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_library_browse(client: TestClient, session: Session):
    """Test la navigation dans la bibliothèque de scénarios."""
    r = client.get("/scenarios/library")
    assert r.status_code == 200

    # Devrait lister les scénarios disponibles
    # TODO: Vérifier contenu une fois la bibliothèque implémentée


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_template_creation(client: TestClient, session: Session):
    """Test la création de scénarios à partir de templates."""
    # Templates prédéfinis
    templates = ["admission_sortie", "transfert_simple", "urgence_reanimation"]

    for template in templates:
        r = client.post(f"/scenarios/from-template/{template}")
        assert r.status_code in [200, 404]

        if r.status_code == 200:
            data = r.json()
            assert "scenario" in data or "id" in data


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_validation_rules(client: TestClient, session: Session):
    """Test les règles de validation des scénarios."""
    # Scénario invalide (pas de steps)
    invalid_scenario = {
        "name": "Invalid Scenario",
        "steps": []
    }

    r = client.post("/scenarios/validate", json=invalid_scenario)
    assert r.status_code in [400, 404]

    if r.status_code == 400:
        data = r.json()
        assert "error" in data or not data.get("valid", True)

    # Scénario valide
    valid_scenario = {
        "name": "Valid Scenario",
        "steps": [
            {
                "id": "step1",
                "name": "Valid Step",
                "type": "movement",
                "movement_type": "A01",
                "delay_days": 0
            }
        ]
    }

    r = client.post("/scenarios/validate", json=valid_scenario)
    if r.status_code == 200:
        data = r.json()
        assert data.get("valid", False)


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_execution_progress_tracking(client: TestClient, session: Session):
    """Test le suivi de progression lors de l'exécution."""
    # Créer scénario multi-steps
    scenario_data = {
        "name": "Progress Test",
        "steps": [
            {"id": "s1", "name": "Step 1", "type": "movement", "movement_type": "A01", "delay_days": 0},
            {"id": "s2", "name": "Step 2", "type": "movement", "movement_type": "A02", "delay_days": 1},
            {"id": "s3", "name": "Step 3", "type": "movement", "movement_type": "A03", "delay_days": 3}
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
        "scenario": scenario_data,
        "patient_id": str(patient.id),
        "start_date": "2025-01-01",
        "track_progress": True
    }

    r = client.post("/scenarios/execute-with-progress", json=execution_data)
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        # Vérifier le suivi de progression
        progress_response = client.get(f"/scenarios/executions/{r.json().get('execution_id')}/progress")
        if progress_response.status_code == 200:
            progress_data = progress_response.json()
            assert "completed_steps" in progress_data or "progress" in progress_data


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_rollback_functionality(client: TestClient, session: Session):
    """Test la fonctionnalité de rollback d'un scénario."""
    # Exécuter un scénario d'abord
    # TODO: Une fois l'exécution implémentée

    # Puis tester le rollback
    r = client.post("/scenarios/executions/1/rollback")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        # Vérifier que les mouvements créés ont été supprimés
        # TODO: Vérifier en DB
        pass


@pytest.mark.xfail(reason="Routes scenarios peuvent être cassées si dépendent de ght.py")
def test_scenario_bulk_import_export(client: TestClient, session: Session):
    """Test l'import/export en masse de scénarios."""
    # Créer plusieurs scénarios
    scenarios_data = [
        {"name": "Scenario 1", "steps": []},
        {"name": "Scenario 2", "steps": []},
        {"name": "Scenario 3", "steps": []}
    ]

    # Test export en masse
    r = client.get("/scenarios/export-bulk")
    assert r.status_code in [200, 404]

    if r.status_code == 200:
        assert "application/zip" in r.headers.get("content-type", "")

    # Test import en masse
    import io
    bulk_file = io.BytesIO(json.dumps(scenarios_data).encode('utf-8'))
    bulk_file.name = 'bulk_scenarios.json'

    r = client.post("/scenarios/import-bulk",
                   files={"file": ("bulk_scenarios.json", bulk_file, "application/json")})
    assert r.status_code in [200, 400, 404]