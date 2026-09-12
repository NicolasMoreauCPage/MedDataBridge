"""Contrat de roundtrip HPRIM pour les quatre catégories d'actes.

Le test passe par les mêmes endpoints que l'IHM : génération, téléchargement
et réintégration. Il remplace le scénario historique, alors marqué xfail, qui
attendait un stockage temporaire sur disque.
"""

import pytest
from fastapi.testclient import TestClient

from app.app import app


client = TestClient(app)


@pytest.mark.parametrize(
    ("act_type", "code", "extra"),
    [
        ("CCAM", "ZZQK900", {"code_activite": "01", "code_phase": "00"}),
        ("NGAP", "AMK", {"coefficient": 1}),
        ("UCD", "1234567890123", {"prix_unitaire": 10.50, "quantite": 2}),
        ("LPP", "1234567890123", {"prix_unitaire": 25.75, "quantite": 1}),
    ],
)
def test_hprim_xml_roundtrip_all_act_types(act_type, code, extra):
    payload = {"type_acte": act_type, "code": code, **extra}

    generated = client.post("/roundtrip-hprim/generate", json=payload)
    assert generated.status_code == 200, generated.text
    generated_body = generated.json()
    assert generated_body["type_acte"] == act_type
    assert generated_body["validation"]["xsd_valid"] is True

    downloaded = client.get(generated_body["download_url"])
    assert downloaded.status_code == 200
    assert b"evenementsServeurActes" in downloaded.content

    reintegrated = client.post(
        "/roundtrip-hprim/reintegrate",
        files={"file": (generated_body["filename"], downloaded.content, "application/xml")},
    )
    assert reintegrated.status_code == 200, reintegrated.text
    body = reintegrated.json()
    assert body["status"] == "ok"
    assert body["message_id"] == generated_body["message_id"]
    assert body["actes_count"] == 1
