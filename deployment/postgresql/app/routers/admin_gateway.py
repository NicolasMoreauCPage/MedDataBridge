"""
Route pour accès à l'interface d'administration SQL.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(tags=["admin"])

@router.get("/admin", response_class=HTMLResponse)
async def admin_gateway(request: Request):
    """Page d'accès à l'interface d'administration SQL."""
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "admin_gateway.html"
    )
