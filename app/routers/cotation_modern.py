"""
Module moderne de cotation - Interface de saisie des prestations médicales.
Intégration HPRIM XML pour codage CCAM, NGAP, UCD, LPP.
"""
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from app.db import get_session
from app.models import Dossier

router = APIRouter(tags=["Cotation Modern"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def cotation_modern_home(
    request: Request,
    dossier_id: int | None = Query(None),
    session: Session = Depends(get_session)
):
    """Page d'accueil du module de cotation moderne.

    Si dossier_id est fourni, redirige vers l'interface de cotation.
    Sinon, affiche la page de sélection de dossier.
    """
    if dossier_id:
        # Vérifier que le dossier existe
        dossier = session.get(Dossier, dossier_id)
        if dossier:
            # Rediriger vers l'interface de cotation
            return RedirectResponse(url=f"/cotation-modern/dossiers/{dossier_id}/cotation", status_code=303)

    # Pas de dossier_id ou dossier non trouvé : afficher le sélecteur
    return templates.TemplateResponse(request, "cotation_selector.html")

@router.get("/dossiers/{dossier_id}/cotation", response_class=HTMLResponse)
def cotation_modern_interface(
    dossier_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Redirige vers l'unique workspace de cotation réellement persistant."""

    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "message": f"Séjour {dossier_id} non trouvé"},
            status_code=404
        )

    return RedirectResponse(url=f"/cotations/dossier/{dossier.id}/saisie", status_code=303)
