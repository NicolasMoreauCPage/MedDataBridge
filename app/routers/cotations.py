"""
Router pour la visualisation et gestion des cotations (CCAM, NGAP, UCD, LPP)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
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
    """
    Vue liste des cotations d'un dossier avec filtres et actions groupées.
    
    Features:
    - Affichage tabulaire de tous les actes (CCAM, NGAP, UCD, LPP)
    - Filtres par type, statut, dates
    - Actions groupées (validation, facturation, suppression)
    - Statistiques rapides
    - Export CSV/Excel
    """
    # Récupérer le dossier
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    # Récupérer le patient
    patient = session.get(Patient, dossier.patient_id) if dossier.patient_id else None
    
    # Récupérer tous les actes CCAM
    ccam_acts = session.exec(
        select(CCAMAct)
        .where(CCAMAct.dossier_id == dossier_id)
        .order_by(CCAMAct.execute_date.desc())
    ).all()
    
    # Récupérer tous les actes NGAP
    ngap_acts = session.exec(
        select(NGAPAct)
        .where(NGAPAct.dossier_id == dossier_id)
        .order_by(NGAPAct.execute_date.desc())
    ).all()
    
    # Récupérer tous les médicaments UCD
    ucd_acts = session.exec(
        select(UCDAct)
        .where(UCDAct.dossier_id == dossier_id)
        .order_by(UCDAct.execute_date.desc())
    ).all()
    
    # Récupérer tous les dispositifs LPP
    lpp_acts = session.exec(
        select(LPPAct)
        .where(LPPAct.dossier_id == dossier_id)
        .order_by(LPPAct.execute_date.desc())
    ).all()
    
    # Compter
    total_actes = len(ccam_acts) + len(ngap_acts) + len(ucd_acts) + len(lpp_acts)
    
    return templates.TemplateResponse(
        "cotations/liste.html",
        {
            "request": request,
            "dossier": dossier,
            "patient": patient,
            "ccam_acts": ccam_acts,
            "ngap_acts": ngap_acts,
            "ucd_acts": ucd_acts,
            "lpp_acts": lpp_acts,
            "total_actes": total_actes,
            "ccam_count": len(ccam_acts),
            "ngap_count": len(ngap_acts),
            "ucd_count": len(ucd_acts),
            "lpp_count": len(lpp_acts)
        }
    )
