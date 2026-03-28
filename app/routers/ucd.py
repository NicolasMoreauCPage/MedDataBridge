"""Module UCD - Unité Commune de Dispensation."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ucd", tags=["UCD"])


@router.get("/", response_class=HTMLResponse)
async def ucd_dashboard(request: Request):
    """Dashboard UCD"""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "module_dashboard.html",
        {
            "request": request,
            "title": "UCD",
            "module_name": "UCD - Unité Commune de Dispensation",
            "module_description": "Centralisez les références UCD et facilitez la saisie des produits de dispensation.",
            "docs_url": "/docs/COTATION_FONCTIONNELLE.md",
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/cotations/api/search/ucd?query=3400",
                    "description": "Recherche de codes UCD (auto-complétion)",
                },
                {
                    "method": "POST",
                    "path": "/api/ucd/",
                    "description": "Création d'un acte UCD pour un dossier",
                },
                {
                    "method": "GET",
                    "path": "/api/ucd/dossier/{dossier_id}",
                    "description": "Historique UCD d'un dossier",
                },
            ],
        },
    )
