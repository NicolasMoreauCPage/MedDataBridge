"""
Module CCAM - Classification Commune des Actes Médicaux (stub).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ccam", tags=["CCAM"])


@router.get("/", response_class=HTMLResponse)
async def ccam_dashboard(request: Request):
    """Dashboard CCAM"""
    return "<html><body><h1>CCAM - Classification Commune des Actes Médicaux</h1><p>Module en développement</p></body></html>"


# TODO: Implémenter la gestion de la nomenclature CCAM
