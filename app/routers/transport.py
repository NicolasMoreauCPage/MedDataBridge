from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Request as FastAPIRequest
from starlette.concurrency import run_in_threadpool
from sqlmodel import Session, select

from app.db import get_session
from app.models.endpoints import SystemEndpoint, MLLPConfig, FHIRConfig, MessageLog
from app.services.mllp import send_mllp
from app.services.fhir_transport import post_fhir_bundle as send_fhir
from app.services.pam import generate_pam_messages_for_dossier
from app.models import Dossier




def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(
    prefix="/transport",
    tags=["transport"],
    responses={404: {"description": "Not found"}}
)

@router.get("/endpoints")
def list_eps(session: Session = Depends(get_session)):
    """List active endpoints with their configs."""
    endpoints = (
        session.exec(select(SystemEndpoint).where(SystemEndpoint.is_enabled.is_(True)))
        .all()
    )
    return [{
        "id": e.id,
        "name": e.name,
        "mllp_configs": [
            {"id": c.id, "name": c.name, "port": c.port, "is_enabled": c.is_enabled}
            for c in e.mllp_configs
        ],
        "fhir_configs": [
            {"id": c.id, "name": c.name, "base_url": c.base_url, "is_enabled": c.is_enabled}
            for c in e.fhir_configs
        ]
    } for e in endpoints]

def _prepare_mllp_delivery(session_factory, dossier_id: int, config_id: int):
    """Charge et génère le lot PAM dans une session courte hors boucle."""
    with session_factory() as session:
        config = session.get(MLLPConfig, config_id)
        dossier = session.get(Dossier, dossier_id)
        if not config or not dossier or not config.is_enabled:
            return None
        session.refresh(dossier, attribute_names=["patient", "venues"])
        for venue in dossier.venues:
            session.refresh(venue, attribute_names=["mouvements"])
        return {
            "endpoint_id": config.endpoint_id,
            "config_id": config.id,
            "host": config.host,
            "port": config.port,
            "messages": generate_pam_messages_for_dossier(dossier),
        }


def _create_transport_log(session_factory, *, kind: str, payload: str, endpoint_id: int, config_id: int, config_kind: str) -> int:
    with session_factory() as session:
        values = {f"{config_kind}_config_id": config_id}
        log = MessageLog(direction="out", kind=kind, endpoint_id=endpoint_id, payload=payload, **values)
        session.add(log)
        session.commit()
        session.refresh(log)
        return log.id


def _complete_transport_log(session_factory, log_id: int, status: str, acknowledgement: object) -> None:
    with session_factory() as session:
        log = session.get(MessageLog, log_id)
        if log is None:
            return
        log.status = status
        log.ack_payload = str(acknowledgement)
        session.add(log)
        session.commit()


@router.post("/send/pam/{dossier_id}/mllp/{config_id}")
async def send_pam_mllp(dossier_id: int, config_id: int, request: Request):
    """Send PAM messages to a specific MLLP config."""
    delivery = await run_in_threadpool(
        _prepare_mllp_delivery,
        request.app.state.session_factory,
        dossier_id,
        config_id,
    )
    if delivery is None:
        raise HTTPException(
            status_code=400,
            detail="Configuration not found or disabled"
        )
    results = []
    for msg in delivery["messages"]:
        log_id = await run_in_threadpool(
            _create_transport_log,
            request.app.state.session_factory,
            kind="MLLP",
            payload=msg,
            endpoint_id=delivery["endpoint_id"],
            config_id=delivery["config_id"],
            config_kind="mllp",
        )
        try:
            ack = await send_mllp(delivery["host"], delivery["port"], msg)
            status = "ack_ok" if "MSA|AA" in ack else "ack_error"
            await run_in_threadpool(
                _complete_transport_log, request.app.state.session_factory, log_id, status, ack
            )
            results.append({"message_id": log_id, "status": status})
        except Exception as ex:
            await run_in_threadpool(
                _complete_transport_log, request.app.state.session_factory, log_id, "error", ex
            )
            results.append({
                "message_id": log_id,
                "status": "error",
                "error": str(ex)
            })
    
    return {"results": results}

def _prepare_fhir_delivery(session_factory, config_id: int):
    with session_factory() as session:
        config = session.get(FHIRConfig, config_id)
        if not config or not config.is_enabled:
            return None
        base_url = config.base_url.rstrip("/")
        path_prefix = config.path_prefix.strip("/")
        return {
            "endpoint_id": config.endpoint_id,
            "config_id": config.id,
            "url": f"{base_url}/{path_prefix}" if path_prefix else base_url,
            "auth_kind": config.auth_kind or "none",
            "auth_token": config.auth_token,
        }


@router.post("/send/fhir/{config_id}")
async def send_fhir_bundle(config_id: int, bundle: dict, request: Request):
    """Send FHIR bundle to a specific FHIR config."""
    delivery = await run_in_threadpool(
        _prepare_fhir_delivery, request.app.state.session_factory, config_id
    )
    if delivery is None:
        raise HTTPException(
            status_code=400,
            detail="Configuration not found or disabled"
        )

    log_id = await run_in_threadpool(
        _create_transport_log,
        request.app.state.session_factory,
        kind="FHIR",
        payload=str(bundle),
        endpoint_id=delivery["endpoint_id"],
        config_id=delivery["config_id"],
        config_kind="fhir",
    )
    status, resp = await send_fhir(
        delivery["url"],
        bundle,
        delivery["auth_kind"],
        delivery["auth_token"],
    )
    log_status = "ack_ok" if status in (200, 201, 202) else "ack_error"
    await run_in_threadpool(
        _complete_transport_log, request.app.state.session_factory, log_id, log_status, resp
    )
    
    return {
        "status": status,
        "response": resp,
        "log_id": log_id
    }
