"""
Router pour l'interface de recherche avancée - Phase 5.3
Utilise l'API FHIR Structure existante (/fhir/Location)
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlmodel import Session
from app.db import get_session
from app.models_structure import EntiteGeographique

router = APIRouter()

# Templates directory
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/structure/search", response_class=HTMLResponse)
async def structure_search_interface(
    request: Request, 
    session: Session = Depends(get_session)
):
    """
    Interface de recherche avancée pour les structures.
    
    Utilise l'API FHIR Structure existante (/fhir/Location) avec :
    - Recherche multi-critères (nom, type, statut, identifiant)
    - Filtres facettes visuels
    - Résultats avec cartes du Design System
    - Historique des recherches
    - Navigation hiérarchique via partof
    """
    
    # Récupérer quelques stats pour l'interface
    eg_count = len(session.query(EntiteGeographique).all())
    
    return templates.TemplateResponse(
        "structure_search.html",
        {
            "request": request,
            "eg_count": eg_count,
            "page_title": "Recherche Avancée Structure"
        }
    )