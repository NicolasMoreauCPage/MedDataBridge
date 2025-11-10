import pytest


def test_health_and_admin_available():
    """Smoke test: ensure health endpoint and admin UI are reachable when full app is available."""
    try:
        from app.app import create_app
        from app.db import get_session
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("Full app not available; skipping admin UI smoke test")

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

        # Admin UI may require auth; just check root of admin exists (200 or redirect)
        r2 = client.get("/admin", allow_redirects=False)
        assert r2.status_code in (200, 302, 401, 403)
