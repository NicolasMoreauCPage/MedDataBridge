"""
Router pour l'interface de recherche avancée - Phase 5.3
Utilise l'API FHIR Structure existante (/fhir/Location)
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlmodel import Session, select
from app.db import get_session
from app.models_structure import EntiteGeographique
from app.templates import templates

router = APIRouter()


@router.get("/structure/search", response_class=HTMLResponse)
def structure_search_interface(
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
    eg_count = session.exec(select(func.count()).select_from(EntiteGeographique)).one()
    
    return templates.TemplateResponse(
        request,
        "structure_search.html",
        {
            "request": request,
            "eg_count": eg_count,
            "title": "Recherche Avancée Structure"
        }
    )
