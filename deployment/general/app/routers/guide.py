from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest



def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(prefix="/guide", tags=["guide"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def user_guide(request: Request):
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "user_guide.html",
    )
