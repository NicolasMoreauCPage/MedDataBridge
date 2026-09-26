"""
Router for Design System Demo - Phase 5.2
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templates import templates

router = APIRouter()


@router.get("/design-system", response_class=HTMLResponse)
async def design_system_demo(request: Request):
    """
    Référence interne de démonstration du Design System Phase 5.2.
    
    Cette page n'est pas un parcours produit et n'est pas exposée dans la
    navigation. Elle permet aux développeurs de vérifier les composants :
    - Palette de couleurs par type et niveau hiérarchique
    - Cartes de structure
    - Indicateurs d'occupation
    - Boutons et formulaires
    - Système de notifications
    - Composants de recherche et filtres
    """
    return templates.TemplateResponse(
        "design_system_demo.html",
        {"request": request, "title": "Design System Hospitalier"}
    )
