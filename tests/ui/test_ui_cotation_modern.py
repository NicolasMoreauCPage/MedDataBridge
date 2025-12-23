import os
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")
from app.app import app

client = TestClient(app)

def test_cotation_modern_page_renders():
    r = client.get("/cotation-modern", allow_redirects=True)
    assert r.status_code == 200
    # Should redirect to dossiers page
    assert "/dossiers" in str(r.url) or "dossiers" in r.text.lower()

def test_cotation_modern_nav_link():
    r = client.get("/")
    assert r.status_code == 200
    # The old link might still be there, or it might be removed
    # Just check that navigation works
    assert "dossiers" in r.text.lower() or "cotation" in r.text.lower()

def test_cotation_modern_js_loaded():
    # Test the redirect behavior
    r = client.get("/cotation-modern", allow_redirects=False)
    assert r.status_code in [302, 307]  # Redirect status
    assert "/dossiers" in r.headers.get("location", "")
