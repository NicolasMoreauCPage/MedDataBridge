"""Module LPP - Liste des Produits et Prestations."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/lpp", tags=["LPP"])


@router.get("/", response_class=HTMLResponse)
async def lpp_dashboard(request: Request):
    """Dashboard LPP"""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "module_dashboard.html",
        {
            "request": request,
            "title": "LPP",
            "module_name": "LPP - Liste des Produits et Prestations",
            "module_description": "Consultez les produits et prestations LPP pour sécuriser le codage des parcours patients.",
            "docs_url": "/docs/COTATION_FONCTIONNELLE.md",
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/cotations/api/search/lpp?query=116",
                    "description": "Recherche de codes LPP (auto-complétion)",
                },
                {
                    "method": "POST",
                    "path": "/api/lpp/",
                    "description": "Création d'un acte LPP pour un dossier",
                },
                {
                    "method": "GET",
                    "path": "/api/lpp/dossier/{dossier_id}",
                    "description": "Historique LPP d'un dossier",
                },
            ],
        },
    )
