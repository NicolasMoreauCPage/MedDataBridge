from fastapi.testclient import TestClient
from app.app import app
from app.db import session_factory
from sqlmodel import select
from app.models_structure import EntiteGeographique, Pole, EntiteJuridique, GHTContext


def test_eg_detail_shows_poles():
    client = TestClient(app)
    # Create minimal fixtures for the test (isolation)
    s = session_factory()
    # Create GHT context
    ght = GHTContext(name="TEST_GHT", code="TEST")
    s.add(ght)
    s.commit()
    s.refresh(ght)

    ej = EntiteJuridique(name="Test EJ", ght_context_id=ght.id)
    s.add(ej)
    s.commit()
    s.refresh(ej)

    eg = EntiteGeographique(name="Test EG", entite_juridique_id=ej.id, identifier="eg-test-1")
    s.add(eg)
    s.commit()
    s.refresh(eg)

    # Add a pole attached to eg
    pole = Pole(name="Pole Test", entite_geo_id=eg.id, identifier="pole-test-1")
    s.add(pole)
    s.commit()
    s.refresh(pole)

    # Request the admin EG page and check content
    resp = client.get(f"/admin/ght/{ght.id}/ej/{ej.id}/eg/{eg.id}")
    assert resp.status_code == 200
    text = resp.text
    # The Solution de repli message should not be present
    assert "Aucun pôle défini" not in text
    # The pole name should be visible
    assert "Pole Test" in text
    s.close()
