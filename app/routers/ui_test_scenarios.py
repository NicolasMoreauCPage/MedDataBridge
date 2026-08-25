"""Interface web minimale pour générer des scénarios de qualification."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui/test-scenarios", tags=["Test Scenarios UI"])


@router.get("", response_class=HTMLResponse)
async def test_scenarios_ui(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "test_scenario_generator.html",
        {"page_title": "Générateur de scénarios de test"},
    )
