"""Module CCAM - Classification Commune des Actes Médicaux."""
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
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/cotations/api/search/ccam?query=HBMD",
                    "description": "Recherche de codes CCAM (auto-complétion)",
                },
                {
                    "method": "POST",
                    "path": "/api/hprim/actes/ccam/emission",
                    "description": "Émission HPRIM XML d'actes CCAM",
                },
                {
                    "method": "GET",
                    "path": "/dossiers/{dossier_id}/cotations",
                    "description": "Workspace de cotations du dossier",
                },
            ],
        },
    )
