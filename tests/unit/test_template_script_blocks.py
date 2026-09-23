def test_scenario_detail_script_block_renders(client, session):
    from app.models_scenarios import InteropScenario
    s = InteropScenario(key="test-scenario", name="Test Scenario", description="d")
    session.add(s)
    session.commit()
    session.refresh(s)
    resp = client.get(f"/scenarios/{s.id}")
    assert resp.status_code == 200
    assert "js/scenario-workspace.js" in resp.text
    assert "data-scenario-workspace" in resp.text


def test_structure_editor_script_is_loaded_only_by_its_workspace(client):
    response = client.get("/structure/interactive")

    assert response.status_code == 200
    assert "js/structure-interactive.js" in response.text


def test_structure_editor_does_not_advertise_unimplemented_deletion_shortcuts():
    from pathlib import Path

    script = Path("app/static/js/structure-interactive.js").read_text(encoding="utf-8")
    template = Path("app/templates/structure_interactive.html").read_text(encoding="utf-8")

    assert "deleteSelected" not in script
    assert "Delete - à implémenter" not in script
    assert "prompt(" not in script
    assert "Del pour supprimer" not in template
    assert "initNativeDragDrop" in script
    assert 'id="structure-duplicate-dialog"' in template


def test_messages_workspaces_load_their_scoped_script_without_inline_handlers(client):
    for path in ("/messages", "/messages/by-dossier"):
        response = client.get(path)

        assert response.status_code == 200
        assert "js/messages-workspace.js" in response.text
        assert "replayMessage(" not in response.text
        assert "loadCotationsForDossiers" not in response.text


def test_conformity_home_script_block_renders(client, session):
    resp = client.get("/conformity")
    assert resp.status_code == 200
    assert "toggle.className" in resp.text


def test_contacts_list_modal_and_script_render(client, session):
    resp = client.get("/contacts")
    assert resp.status_code == 200
    assert "deleteModal" in resp.text
    assert "Gestion des suppressions asynchrones" in resp.text


def test_qualification_dashboard_renders_with_the_test_bench_entrypoint(client):
    resp = client.get("/ui/interface-testing")

    assert resp.status_code == 200
    assert "Le laboratoire des échanges partenaires" in resp.text
    assert 'action="/ui/interface-testing/runs"' in resp.text


def test_plan_lits_assignment_creates_a_traceable_transfer(client, session):
    from datetime import datetime, timezone

    from sqlmodel import select

    from app.models import Dossier, Mouvement, Patient, Venue
    from app.models_structure import Lit

    patient = Patient(patient_seq=9001, identifier="IPP-9001", family="MARTIN", given="Anne")
    session.add(patient)
    session.flush()
    dossier = Dossier(dossier_seq=9001, patient_id=patient.id, admit_time=datetime.now(timezone.utc))
    session.add(dossier)
    session.flush()
    venue = Venue(venue_seq=9001, dossier_id=dossier.id, start_time=datetime.now(timezone.utc))
    lit = Lit(identifier="LIT-UX-9001", name="Lit UX")
    session.add(venue)
    session.add(lit)
    session.commit()
    session.refresh(lit)

    resp = client.post(
        "/mouvements/plan-lits/assign",
        data={"lit_id": lit.id, "selected_patient_id": patient.id},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    session.refresh(venue)
    assert venue.lit_id == lit.id
    movement = session.exec(select(Mouvement).where(Mouvement.venue_id == venue.id)).one()
    assert (movement.type, movement.trigger_event, movement.movement_type) == ("ADT^A02", "A02", "transfer")
