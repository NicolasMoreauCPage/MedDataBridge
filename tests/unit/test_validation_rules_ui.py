def test_validation_rules_workspace_renders(client) -> None:
    response = client.get("/validation/rules")

    assert response.status_code == 200
    assert "Règles de validation" in response.text
    assert 'aria-live="polite"' in response.text
    assert "js/validation-rules-workspace.js" in response.text
    assert "Les modifications non sauvegardées seront perdues." not in response.text
    assert "window.PameliaUi.confirm" not in response.text


def test_validation_rules_api_saves_the_json_payload(client, monkeypatch) -> None:
    from app.routers import validation_rules

    saved = {}

    def capture_write(payload: dict) -> None:
        saved["payload"] = payload

    monkeypatch.setattr(validation_rules, "_write_rules", capture_write)

    response = client.post("/api/validation-rules", json={"ZBE": {"required": True}})

    assert response.status_code == 200
    assert response.json() == {"message": "Règles sauvegardées"}
    assert saved["payload"] == {"ZBE": {"required": True}}
