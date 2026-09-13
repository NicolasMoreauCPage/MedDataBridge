def test_monitoring_dashboard_uses_french_operator_labels(client) -> None:
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Tableau de bord de supervision" in response.text
    assert "Durée des opérations (ms)" in response.text
    assert "Synthèse des opérations" in response.text
    assert 'id="btn-reset-metrics"' in response.text
