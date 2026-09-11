"""Parcours IHM critique du validateur IHE PAM France."""

import os

from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

from app.app import app


def test_validation_report_exposes_a_clickable_structured_field_view():
    """Un intégrateur doit pouvoir passer du diagnostic au champ HL7 concerné."""
    message = "\r".join([
        "MSH|^~\\&|S|F|R|F|202601010101||ADT^A01^ADT_A39|M1|P|2.5^FRA^2.11|||||FRA|UNICODE UTF-8",
        "EVN|A01|202601010101",
        "PID|1||P1^^^HOSP^PI||DOE^JOHN||19800101|M||||||||||||||||||||||||VALI",
        "PV1|1|I|WARD^101^A||||||||||||||||V1^^^HOSP^VN",
        "ZBE|MVT1^HOSP^1.2.3^ISO|202601010101||INSERT|N|||^^^^^^^^^UF1|H",
    ])

    response = TestClient(app).post(
        "/validation/validate",
        data={"hl7_message": message, "direction": "in"},
    )

    assert response.status_code == 200
    assert "Message décodé" in response.text
    assert 'id="MSH_9"' in response.text
    assert "voir le champ" in response.text
    assert "IHE PAM International" not in response.text
