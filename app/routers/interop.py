# app/routers/interop.py
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from app.db import get_session
from app.models.endpoints import SystemEndpoint

router = APIRouter(prefix="/interop", tags=["interop"])
logger = logging.getLogger(__name__)

def _get_mllp_endpoint(session_factory, endpoint_id: int):
    with session_factory() as session:
        return session.get(SystemEndpoint, endpoint_id)


@router.post("/mllp/start/{endpoint_id}")
async def start_endpoint(endpoint_id: int, request: Request):
    e = await run_in_threadpool(
        _get_mllp_endpoint,
        request.app.state.session_factory,
        endpoint_id,
    )
    if not e or e.kind != "MLLP":
        return JSONResponse({"error": "Endpoint non trouvé ou pas MLLP"}, status_code=400)
    await request.app.state.mllp_manager.start_endpoint(e)
    return {"message": f"MLLP '{e.name}' démarré sur {e.host}:{e.port}"}

@router.post("/mllp/stop/{endpoint_id}")
async def stop_endpoint(endpoint_id: int, request: Request):
    await request.app.state.mllp_manager.stop_endpoint(endpoint_id)
    return {"message": f"MLLP endpoint {endpoint_id} arrêté"}

@router.post("/mllp/reload")
async def reload_all(request: Request, session=Depends(get_session)):
    await request.app.state.mllp_manager.reload_all(session)
    return {"message": "Tous les serveurs MLLP ont été rechargés", "running": request.app.state.mllp_manager.running_ids()}


@router.get("/mllp/status")
def mllp_status(request: Request):
    mgr = request.app.state.mllp_manager
    running = mgr.running_ids()
    # Si tu veux aussi renvoyer les (host,port)
    bindings = []
    for eid, srv in mgr.servers.items():
        try:
            s = srv.sockets[0]
            host, port = s.getsockname()[:2]
            bindings.append({"endpoint_id": eid, "host": host, "port": port})
        except (AttributeError, IndexError, OSError):
            # Une socket peut disparaître pendant un reload; le serveur reste
            # visible comme actif mais son binding est momentanément absent.
            logger.debug("MLLP binding unavailable endpoint_id=%s", eid, exc_info=True)
    return {"running_ids": running, "bindings": bindings}
