from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models_shared import MessageLog


def test_fhir_inbox_reception_storage_ack(client: TestClient, session: Session):
    """Valide le flux réception -> stockage -> acquittement pour l'inbox FHIR."""
    initial_count = len(session.exec(select(MessageLog)).all())

    payload = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "pat-001",
                    "name": [{"family": "DUPONT", "given": ["ALICE"]}],
                }
            }
        ],
    }

    response = client.post("/inbox/fhir", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["code"] == "informational"

    logs = session.exec(select(MessageLog).order_by(MessageLog.id.desc())).all()
    assert len(logs) >= initial_count + 1

    latest = logs[0]
    assert latest.kind == "FHIR"
    assert latest.direction == "in"
    assert latest.status == "ack_ok"
    assert "Patient" in latest.payload
    assert "OperationOutcome" in (latest.ack_payload or "")
