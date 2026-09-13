def test_validation_rules_workspace_renders(client) -> None:
    response = client.get("/validation/rules")

    assert response.status_code == 200
    assert "Règles de validation" in response.text
