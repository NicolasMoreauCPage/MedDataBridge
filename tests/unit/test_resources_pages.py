from fastapi.testclient import TestClient
from app.app import app

client = TestClient(app)

def test_examples_hl7v2():
    r = client.get("/examples/hl7v2")
    assert r.status_code == 200
    assert "Exemples HL7 v2" in r.text

def test_tools_mllp():
    r = client.get("/tools/mllp")
    assert r.status_code == 200
    assert "Guide de connexion MLLP" in r.text

def test_endpoints_test():
    r = client.get("/tools/endpoints-test")
    assert r.status_code == 200
    assert "Endpoints de test" in r.text
