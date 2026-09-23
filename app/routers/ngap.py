# app/routers/ngap.py
"""
Routes web pour la gestion des actes NGAP
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func

from app.db import get_session
from app.models import Dossier, NGAPAct
from app.services.ngap_service import NGAPService, NGAPActCreate

router = APIRouter(prefix="/ngap", tags=["NGAP Web"])
templates = Jinja2Templates(directory="app/templates")


def _fr_datetime(value):
    """Même format que le filtre `fr_datetime` global (app/app.py) — dupliqué ici car ce
    routeur utilise sa propre instance Jinja2Templates plutôt que celle partagée de l'app."""
    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M%S", "%Y%m%d"):
            try:
                value = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            return value
    try:
        return value.strftime("%d/%m/%Y %H:%M")
    except (AttributeError, ValueError):
        return value


templates.env.filters["fr_datetime"] = _fr_datetime


@router.get("/")
def ngap_dashboard(request: Request, db: Session = Depends(get_session)):
    """Dashboard NGAP avec statistiques réelles."""
    total_acts = db.exec(select(func.count()).select_from(NGAPAct)).one()

    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    acts_this_month = db.exec(
        select(func.count()).select_from(NGAPAct).where(NGAPAct.execute_date >= month_start)
    ).one()

    active_dossiers = db.exec(
        select(func.count(func.distinct(NGAPAct.dossier_id)))
        .select_from(NGAPAct)
        .join(Dossier, Dossier.id == NGAPAct.dossier_id)
        .where(Dossier.discharge_time.is_(None))
    ).one()

    valid_acts = db.exec(select(func.count()).select_from(NGAPAct).where(NGAPAct.valide == True)).one()  # noqa: E712
    conformity_rate = round(100 * valid_acts / total_acts) if total_acts else 0

    return templates.TemplateResponse("ngap/dashboard.html", {
        "request": request,
        "title": "Gestion NGAP",
        "total_acts": total_acts,
        "acts_this_month": acts_this_month,
        "active_dossiers": active_dossiers,
        "conformity_rate": conformity_rate,
    })


@router.get("/dossier/{dossier_id}")
def ngap_by_dossier(
    request: Request,
    dossier_id: int,
    db: Session = Depends(get_session)
):
    """Actes NGAP d'un dossier"""
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    service = NGAPService(db)
    acts = service.get_acts_by_dossier(dossier_id)

    return templates.TemplateResponse("ngap/dossier_acts.html", {
        "request": request,
        "dossier": dossier,
        "acts": acts,
        "title": f"NGAP - Dossier #{dossier.dossier_seq}"
    })


@router.get("/create/{dossier_id}")
def create_ngap_form(
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
def create_ngap_act(
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
    dossier = db.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

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
    act = service.create_act(act_data)

    return templates.TemplateResponse("ngap/act_created.html", {
        "request": request,
        "act": act,
        "title": "Acte NGAP créé"
    })
