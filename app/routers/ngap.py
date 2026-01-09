# app/routers/ngap.py
"""
Routes web pour la gestion des actes NGAP
"""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db import get_session
from app.models import Dossier, NGAPAct
from app.services.ngap_service import NGAPService, NGAPActCreate

router = APIRouter(prefix="/ngap", tags=["NGAP Web"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def ngap_dashboard(request: Request, db: Session = Depends(get_session)):
    """Dashboard NGAP"""
    return templates.TemplateResponse("ngap/dashboard.html", {
        "request": request,
        "title": "Gestion NGAP"
    })


@router.get("/dossier/{dossier_id}")
async def ngap_by_dossier(
    request: Request,
    dossier_id: int,
    db: Session = Depends(get_session)
):
    """Actes NGAP d'un dossier"""
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    service = NGAPService(db)
    acts = await service.get_acts_by_dossier(dossier_id)

    return templates.TemplateResponse("ngap/dossier_acts.html", {
        "request": request,
        "dossier": dossier,
        "acts": acts,
        "title": f"NGAP - Dossier #{dossier.dossier_seq}"
    })


@router.get("/create/{dossier_id}")
async def create_ngap_form(
    request: Request,
    dossier_id: int,
    db: Session = Depends(get_session)
):
    """Formulaire de création d'acte NGAP"""
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    return templates.TemplateResponse("ngap/create_form.html", {
        "request": request,
        "dossier": dossier,
        "title": f"Nouveau NGAP - Dossier #{dossier.dossier_seq}"
    })


@router.post("/create/{dossier_id}")
async def create_ngap_act(
    request: Request,
    dossier_id: int,
    lettre_cle: str = Form(...),
    coefficient: float = Form(...),
    execute_date: str = Form(...),
    prestataire_id: Optional[int] = Form(None),
    denombrement: Optional[int] = Form(None),
    position_dentaire: Optional[str] = Form(None),
    execute_heure: Optional[str] = Form(None),
    numero_seance: Optional[int] = Form(None),
    montant: Optional[float] = Form(None),
    commentaire: Optional[str] = Form(None),
    db: Session = Depends(get_session)
):
    """Créer un acte NGAP"""
    try:
        execute_datetime = datetime.fromisoformat(execute_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date invalide")

    act_data = NGAPActCreate(
        dossier_id=dossier_id,
        lettre_cle=lettre_cle,
        coefficient=coefficient,
        execute_date=execute_datetime,
        prestataire_id=prestataire_id,
        denombrement=denombrement,
        position_dentaire=position_dentaire,
        execute_heure=execute_heure,
        numero_seance=numero_seance,
        montant=montant,
        commentaire=commentaire
    )

    service = NGAPService(db)
    act = await service.create_act(act_data)

    return templates.TemplateResponse("ngap/act_created.html", {
        "request": request,
        "act": act,
        "title": "Acte NGAP créé"
    })