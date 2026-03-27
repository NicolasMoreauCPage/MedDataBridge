"""
Module CCAM - Classification Commune des Actes Médicaux (stub).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ccam", tags=["CCAM"])


@router.get("/", response_class=HTMLResponse)
async def ccam_dashboard(request: Request):
    """Dashboard CCAM"""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "module_dashboard.html",
        {
            "request": request,
            "title": "CCAM",
            "module_name": "CCAM - Classification Commune des Actes Médicaux",
            "module_description": "Recherchez et exploitez les actes CCAM dans les parcours de codage et de facturation.",
            "docs_url": "/docs/COTATION_FONCTIONNELLE.md",
            "endpoints": [],
        },
    )


# TODO: Implémenter la gestion de la nomenclature CCAM
