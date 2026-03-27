"""
Module LPP - Liste des Produits et Prestations (stub).
"""
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
            "endpoints": [],
        },
    )


# TODO: Implémenter la gestion de la nomenclature LPP
