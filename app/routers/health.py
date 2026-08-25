from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health/live")
def health_live():
    """Liveness probe independent from database and cache availability."""
    return {"status": "ok"}

@router.get("/api/version")
def get_version(request: Request):
    """Return application version"""
    version = getattr(request.app.state, "version", "0.2.0")
    return {"version": version, "app": "MedData_Bridge"}
