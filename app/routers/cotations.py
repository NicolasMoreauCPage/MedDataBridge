"""
Router pour la visualisation et gestion des cotations (CCAM, NGAP, UCD, LPP)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional

from app.db import get_session
from app.models import Dossier, Patient, CCAMAct, NGAPAct, UCDAct, LPPAct

router = APIRouter(prefix="/dossiers", tags=["cotations"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{dossier_id}/cotations", response_class=HTMLResponse, name="cotations_liste")
async def get_dossier_cotations(
    request: Request,
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Ancienne vue liste : redirigée vers le workspace unique de saisie rapide."""

    # Vérifier l'existence du dossier pour garder un comportement d'erreur cohérent
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    # Rediriger vers la nouvelle vue unifiée saisie + liste
    return RedirectResponse(url=f"/cotations/dossier/{dossier_id}/saisie", status_code=302)
