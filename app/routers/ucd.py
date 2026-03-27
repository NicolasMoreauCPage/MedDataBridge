"""
Module UCD - Unité Commune de Dispensation (stub).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ucd", tags=["UCD"])


@router.get("/", response_class=HTMLResponse)
async def ucd_dashboard(request: Request):
    """Dashboard UCD"""
    return "<html><body><h1>UCD - Unité Commune de Dispensation</h1><p>Module en développement</p></body></html>"


# TODO: Implémenter la gestion de la nomenclature UCD
