"""
Route pour accès à l'interface d'administration SQL.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/admin", response_class=HTMLResponse)
async def admin_gateway(request: Request):
    """Page d'accès à l'interface d'administration SQL."""
    return templates.TemplateResponse(
        "admin_gateway.html",
        {"request": request}
    )
