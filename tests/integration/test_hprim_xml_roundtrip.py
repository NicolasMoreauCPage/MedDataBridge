import os
import pytest
from fastapi.testclient import TestClient
from app.app import app

client = TestClient(app)

@pytest.mark.parametrize("cotation", [
    {"type": "CCAM", "code": "ZZQK900"},
    {"type": "NGAP", "code": "AMK"},
    {"type": "UCD", "code": "1234567890123", "montant": 10.50},
    {"type": "LPP", "code": "1234567890123", "montant": 25.75},
])
def test_hprim_xml_roundtrip(cotation):
    # 1. Générer le message HPRIM XML
    resp = client.post("/roundtrip-hprim/generate", json=cotation)
    assert resp.status_code == 200
    data = resp.json()
    assert "filepath" in data
    filepath = data["filepath"]
    assert os.path.exists(filepath)

    # 2. Télécharger le message généré
    filename = data["filename"]
    resp = client.get(f"/roundtrip-hprim/download/{filename}")
    assert resp.status_code == 200
    xml_content = resp.content
    # Vérifie que le root XML correspond au schéma attendu (ex: <evenementsServeurActes> pour CCAM)
    assert b"<evenementsServeurActes" in xml_content or b"<ns0:evenementsServeurActes" in xml_content or b"<evenementServeurActes" in xml_content or b"<ns0:evenementServeurActes" in xml_content or b"<evenementServeurUCD" in xml_content or b"<ns0:evenementServeurUCD" in xml_content or b"<evenementServeurLPP" in xml_content or b"<ns0:evenementServeurLPP" in xml_content

    # 3. Réintégrer le message (upload)
    files = {"file": (filename, xml_content, "application/xml")}
    resp = client.post("/roundtrip-hprim/reintegrate", files=files)
    assert resp.status_code == 200
    reintegrate_data = resp.json()
    assert reintegrate_data["status"] == "ok"
    assert reintegrate_data["filename"] == filename
    assert os.path.exists(reintegrate_data["saved_to"])
