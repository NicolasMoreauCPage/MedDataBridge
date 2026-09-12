import json

from fastapi.testclient import TestClient
from sqlmodel import select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_identifiers import Identifier
from app.models_structure import EntiteJuridique, GHTContext


def test_messages_send_fhir_imports_a_single_resource(client: TestClient, session):
    ght = GHTContext(name="GHT FHIR formulaire", code="GHT-FHIR-FORM")
    session.add(ght)
    session.flush()
    ej = EntiteJuridique(identifier="EJ-FHIR-FORM", name="EJ FHIR formulaire", ght_context_id=ght.id)
    session.add(ej)
    session.flush()
    endpoint = SystemEndpoint(
        name="FHIR entrant formulaire", kind="FHIR", role="receiver", is_enabled=True,
        entite_juridique_id=ej.id,
    )
    session.add(endpoint)
    session.commit()

    resource = {
        "resourceType": "Patient",
        "id": "form-patient-1",
        "identifier": [{"system": "urn:test:ipp", "value": "IPP-FORM-1"}],
        "name": [{"family": "DUPONT", "given": ["Alice"]}],
        "gender": "female",
        "birthDate": "1980-01-02",
    }
    response = client.post("/messages/send", data={
        "kind": "FHIR", "endpoint_id": str(endpoint.id), "payload": json.dumps(resource),
    })

    assert response.status_code == 200
    session.expire_all()
    assert session.exec(select(Identifier).where(Identifier.value == "IPP-FORM-1")).one()
    log = session.exec(
        select(MessageLog).where(MessageLog.endpoint_id == endpoint.id).order_by(MessageLog.id.desc())
    ).first()
    assert log is not None
    assert log.status == "ack_ok"
    assert "Import FHIR" in (log.ack_payload or "")
