def test_cotation_modern_page_renders(client):
    r = client.get("/cotation-modern/", follow_redirects=False)
    assert r.status_code == 200
    assert "Codage des Prestations Médicales" in r.text
    assert "Sélectionnez le séjour patient" in r.text

def test_cotation_modern_nav_link(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "dossiers" in r.text.lower() or "cotation" in r.text.lower()

def test_cotation_modern_selector_loads_search_workflow(client):
    r = client.get("/cotation-modern/", follow_redirects=False)
    assert r.status_code == 200
    assert "/cotation-modern/search" in r.text
    assert "/cotation-modern/dossiers/${d.dossier_id}/cotation" in r.text
