"""
Router for Design System Demo - Phase 5.2
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()

# Templates directory
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/design-system", response_class=HTMLResponse)
async def design_system_demo(request: Request):
    """
    Page de démonstration du Design System Phase 5.2
    
    Affiche tous les composants réutilisables :
    - Palette de couleurs par type et niveau hiérarchique
    - Cartes de structure
    - Indicateurs d'occupation
    - Boutons et formulaires
    - Système de notifications
    - Composants de recherche et filtres
    """
    return templates.TemplateResponse(
        "design_system_demo.html",
        {"request": request}
    )
