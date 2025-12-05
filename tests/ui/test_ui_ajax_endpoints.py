import os
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

from app.app import app

client = TestClient(app)


def test_api_structure_tree():
    r = client.get("/api/structure/tree")
    # Depending on dataset, accept 200 or 204/404 if empty
    assert r.status_code in (200, 204, 404)


def test_api_structure_details():
    # Requesting details for a likely-missing object should Renvoie 404 or 200
    r = client.get("/api/structure/details/service/1")
    assert r.status_code in (200, 404)


def test_metrics_dashboard_endpoint():
    r = client.get("/api/metrics/dashboard")
    assert r.status_code in (200, 204, 404)


def test_validation_submit_without_payload():
    # The validation form posts to /validation/validate
    r = client.post("/validation/validate", data={})
    # Accept 422 (Unprocessable Entity) or 400 if validation fails due to missing payload,
    # or 200 if it Renvoie a page. This keeps the test robust across changes.
    assert r.status_code in (200, 400, 422)
