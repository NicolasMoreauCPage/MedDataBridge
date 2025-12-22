import os
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")
from app.app import app

client = TestClient(app)

def test_cotation_modern_page_renders():
    r = client.get("/cotation-modern")
    assert r.status_code == 200
    assert "Cotation HPRIM" in r.text or "cotation" in r.text.lower()
    assert "form" in r.text.lower() or "acte" in r.text.lower()

def test_cotation_modern_nav_link():
    r = client.get("/")
    assert r.status_code == 200
    assert "/cotation-modern" in r.text

def test_cotation_modern_js_loaded():
    r = client.get("/cotation-modern")
    assert r.status_code == 200
    # JS file should be referenced
    assert "/static/js/cotationForm.js" in r.text
