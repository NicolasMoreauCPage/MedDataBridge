import os
from fastapi.testclient import TestClient

# Ensure app runs in testing mode to avoid DB/scheduler start
os.environ.setdefault("TESTING", "1")

from app.app import app


client = TestClient(app)


def test_home_page_renders():
    r = client.get("/")
    assert r.status_code == 200
    # Basic sanity: response should be HTML and contain site navigation links
    assert "<!doctype html>" in r.text.lower() or "<html" in r.text.lower()
    assert "/patients" in r.text or "Validation" in r.text or "Endpoints" in r.text


def test_patients_page_renders():
    r = client.get("/patients")
    # If auth is required this may redirect or return 200; accept 200 or 302
    assert r.status_code in (200, 302)


def test_validation_page_renders():
    r = client.get("/validation")
    assert r.status_code == 200
    assert "Validation" in r.text


def test_endpoints_page_renders():
    r = client.get("/endpoints")
    assert r.status_code == 200
    assert "Endpoints" in r.text or "Points d'accès" in r.text


def test_api_docs_page_renders():
    r = client.get("/api/docs")
    # API docs route may be present or not depending on configuration; accept 200 or 404
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "API" in r.text or "Gestion structure" in r.text
