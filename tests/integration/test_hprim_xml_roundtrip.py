"""Contrat de roundtrip HPRIM pour les quatre catégories d'actes.

Le test passe par les mêmes endpoints que l'IHM : génération, téléchargement
et réintégration. Il remplace le scénario historique, alors marqué xfail, qui
attendait un stockage temporaire sur disque.
"""

import re

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


def test_hprim_rejects_a_compact_hl7_date_in_an_act():
    """Une date d'acte HPRIM est un xs:date, pas une date HL7 compacte."""
    generated = client.post("/roundtrip-hprim/generate", json={"type_acte": "CCAM", "code": "ZZQK900"})
    assert generated.status_code == 200, generated.text
    downloaded = client.get(generated.json()["download_url"])
    invalid_xml = re.sub(
        r"(<(?:[A-Za-z0-9_]+:)?execute>\s*<(?:[A-Za-z0-9_]+:)?date>)\d{4}-\d{2}-\d{2}(</(?:[A-Za-z0-9_]+:)?date>)",
        r"\g<1>20260912\g<2>",
        downloaded.content.decode("iso-8859-1"),
        count=1,
    )
    assert "20260912" in invalid_xml

    reintegrated = client.post(
        "/roundtrip-hprim/reintegrate",
        files={"file": ("date-invalide.xml", invalid_xml.encode("iso-8859-1"), "application/xml")},
    )
    assert reintegrated.status_code == 200
    body = reintegrated.json()
    assert body["status"] == "error"
    assert "xs:date" in body["erreurs"][0]
