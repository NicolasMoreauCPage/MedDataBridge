"""
Module moderne de cotation - Interface de saisie des prestations médicales.
Intégration HPRIM XML pour codage CCAM, NGAP, UCD, LPP.
"""
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.db import get_session
from app.models import Dossier, Patient
import os

router = APIRouter(tags=["Cotation Modern"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def cotation_modern_home(
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
    return templates.TemplateResponse("cotation_selector.html", {"request": request})

@router.get("/dossiers/{dossier_id}/cotation", response_class=HTMLResponse)
async def cotation_modern_interface(
    dossier_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """Interface principale de cotation HPRIM (CCAM, NGAP, UCD, LPP).
    
    Affiche le formulaire de saisie des prestations médicales pour le séjour.
    """
    # Charger le dossier et le patient
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": f"Séjour {dossier_id} non trouvé"},
            status_code=404
        )
    
    # Charger le patient associé
    patient = session.get(Patient, dossier.patient_id) if dossier.patient_id else None
    
    return templates.TemplateResponse(
        "hprim_cotation_modern.html",
        {
            "request": request,
            "dossier": dossier,
            "patient": patient
        }
    )
