from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health")
def health_check():
    """Health check endpoint for tests"""
    return {"status": "ok"}

@router.get("/api/version")
def get_version(request: Request):
    """Return application version"""
    version = getattr(request.app.state, "version", "0.2.0")
    return {"version": version, "app": "MedData_Bridge"}