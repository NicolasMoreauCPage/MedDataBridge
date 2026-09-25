"""Transport routes keep SQL work outside their asynchronous network phase."""

from fastapi.testclient import TestClient


def test_transport_routes_validate_configuration_in_a_short_session(client: TestClient):
    response = client.post("/transport/send/pam/999/mllp/999")

    assert response.status_code == 400
    assert response.json()["detail"] == "Configuration not found or disabled"
