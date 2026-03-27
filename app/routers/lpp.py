"""
Module LPP - Liste des Produits et Prestations (stub).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/lpp", tags=["LPP"])


@router.get("/", response_class=HTMLResponse)
async def lpp_dashboard(request: Request):
    """Dashboard LPP"""
    return "<html><body><h1>LPP - Liste des Produits et Prestations</h1><p>Module en développement</p></body></html>"


# TODO: Implémenter la gestion de la nomenclature LPP
