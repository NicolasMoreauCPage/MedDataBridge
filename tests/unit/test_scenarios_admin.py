from fastapi.testclient import TestClient

from app.app import app
from app.models_scenarios import InteropScenario


def test_scenarios_admin_lists_inactive_scenarios_and_can_toggle_them(session):
    scenario = InteropScenario(
        key="admin.inactive.scenario",
        name="Scénario à corriger",
        is_active=False,
    )
    session.add(scenario)
    session.commit()
    session.refresh(scenario)

    client = TestClient(app)
    page = client.get("/scenarios/admin?active=inactive")
    assert page.status_code == 200
    assert "Scénario à corriger" in page.text
    assert "Administration des scénarios" in page.text

    response = client.post(
        f"/scenarios/{scenario.id}/admin/toggle",
        data={"is_active": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    session.refresh(scenario)
    assert scenario.is_active is True
