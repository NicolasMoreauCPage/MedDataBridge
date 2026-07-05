def test_scenario_detail_script_block_renders(client, session):
    from app.models_scenarios import InteropScenario
    s = InteropScenario(key="test-scenario", name="Test Scenario", description="d")
    session.add(s)
    session.commit()
    session.refresh(s)
    resp = client.get(f"/scenarios/{s.id}")
    assert resp.status_code == 200
    assert "configureRealisticTiming" in resp.text


def test_conformity_home_script_block_renders(client, session):
    resp = client.get("/conformity")
    assert resp.status_code == 200
    assert "toggle.className" in resp.text


def test_contacts_list_modal_and_script_render(client, session):
    resp = client.get("/contacts")
    assert resp.status_code == 200
    assert "deleteModal" in resp.text
    assert "Gestion des suppressions asynchrones" in resp.text


def test_hprim_cotation_modern_uses_shared_toast_system(client, session):
    from app.models import Patient, Dossier
    from datetime import datetime, timezone
    p = Patient(patient_seq=1, identifier="IPP900", family="X", given="Y")
    session.add(p)
    session.flush()
    d = Dossier(dossier_seq=1, patient_id=p.id, admit_time=datetime.now(timezone.utc))
    session.add(d)
    session.commit()
    session.refresh(d)
    resp = client.get(f"/cotation-modern/dossiers/{d.id}/cotation")
    assert resp.status_code == 200
    assert "window.toastSystem.show" in resp.text
    assert 'id="toastStack"' not in resp.text
    assert resp.text.count('id="toast-container"') == 1
