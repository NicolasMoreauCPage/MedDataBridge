def test_validation_rules_workspace_renders(client) -> None:
    response = client.get("/validation/rules")

    assert response.status_code == 200
    assert "Règles de validation" in response.text
    assert 'aria-live="polite"' in response.text
    assert "Les modifications non sauvegardées seront perdues." in response.text
    assert "window.PameliaUi.confirm" in response.text
