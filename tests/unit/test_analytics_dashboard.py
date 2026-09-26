"""Régressions du tableau de bord d'exploitation."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models_structure import EntiteGeographique


def test_analytics_dashboard_uses_the_requested_geographical_entity(client: TestClient, session: Session) -> None:
    eg = EntiteGeographique(identifier="EG-ANALYTICS", name="EG Analytics")
    session.add(eg)
    session.commit()
    session.refresh(eg)

    response = client.get(f"/structure/analytics?eg_id={eg.id}")

    assert response.status_code == 200
    assert f'data-eg-id="{eg.id}"' in response.text
    assert "js/analytics-dashboard-workspace.js" in response.text
    assert f"eg_id={eg.id}&amp;period=30d" in response.text


def test_analytics_kpis_returns_an_empty_scope_without_loading_domain_rows(client: TestClient) -> None:
    response = client.get("/api/analytics/kpis?period=30d")

    assert response.status_code == 200
    assert response.json()["total_beds"] == 0
    assert response.json()["available_beds"] == 0
