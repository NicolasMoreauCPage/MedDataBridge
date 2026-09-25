from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.db import get_session
from app.dependencies.request_data import read_body
from app.models_endpoints import MessageLog

router = APIRouter(prefix="/inbox/fhir", tags=["inbox-fhir"])

@router.post("")
def receive_fhir(body: bytes = Depends(read_body), session=Depends(get_session)):
    # Reçoit un Bundle/Resource FHIR en JSON
    log = MessageLog(direction="in", kind="FHIR", payload=body.decode("utf-8"), status="received")
    session.add(log)
    session.commit()
    outcome = {
        "resourceType": "OperationOutcome",
        "issue": [{"severity":"information","code":"informational","diagnostics":"Received"}]
    }
    log.ack_payload = str(outcome)
    log.status = "ack_ok"
    session.add(log)
    session.commit()
    return JSONResponse(outcome, status_code=201)
