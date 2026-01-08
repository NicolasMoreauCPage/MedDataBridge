# app/api/ccam.py
"""
API endpoints pour la gestion des actes CCAM
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.db import get_session
from app.models import CCAMAct, Dossier
from app.models_practitioners import MedecinResponsable
from app.services.ccam_service import CCAMService

router = APIRouter(prefix="/api/ccam", tags=["CCAM"])


class CCAMActCreate(BaseModel):
    dossier_id: int
    code_acte: str
    code_activite: str
    code_phase: Optional[str] = None
    modificateurs: Optional[List[str]] = None
    execute_date: datetime
    execute_heure: Optional[str] = None
    quantite: int = 1
    montant: Optional[float] = None
    extension: Optional[str] = None
    executant_id: Optional[int] = None
    prescripteur_id: Optional[int] = None
    commentaire: Optional[str] = None


class CCAMActResponse(BaseModel):
    id: int
    dossier_id: int
    code_acte: str
    code_activite: str
    code_phase: Optional[str]
    modificateurs: Optional[str]
    execute_date: datetime
    execute_heure: Optional[str]
    quantite: int
    montant: Optional[float]
    extension: Optional[str]
    executant_id: Optional[int]
    prescripteur_id: Optional[int]
    commentaire: Optional[str]
    facturable: bool
    valide: bool
    facture: bool
    created_at: datetime
    updated_at: datetime


class CCAMActUpdate(BaseModel):
    valide: Optional[bool] = None
    commentaire: Optional[str] = None


@router.post("/acts", response_model=CCAMActResponse)
def create_ccam_act(act_data: CCAMActCreate, session: Session = Depends(get_session)):
    """Créer un nouvel acte CCAM"""
    try:
        act = CCAMService.create_act(
            session=session,
            dossier_id=act_data.dossier_id,
            code_acte=act_data.code_acte,
            code_activite=act_data.code_activite,
            code_phase=act_data.code_phase,
            modificateurs=act_data.modificateurs,
            execute_date=act_data.execute_date,
            execute_heure=act_data.execute_heure,
            quantite=act_data.quantite,
            montant=act_data.montant,
            extension=act_data.extension,
            executant_id=act_data.executant_id,
            prescripteur_id=act_data.prescripteur_id,
            commentaire=act_data.commentaire
        )
        return CCAMActResponse(**act.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/acts/dossier/{dossier_id}", response_model=List[CCAMActResponse])
def get_ccam_acts_by_dossier(dossier_id: int, session: Session = Depends(get_session)):
    """Récupérer les actes CCAM d'un dossier"""
    acts = CCAMService.get_acts_by_dossier(session, dossier_id)
    return [CCAMActResponse(**act.__dict__) for act in acts]


@router.get("/acts/{act_id}", response_model=CCAMActResponse)
def get_ccam_act(act_id: int, session: Session = Depends(get_session)):
    """Récupérer un acte CCAM par son ID"""
    act = CCAMService.get_act_by_id(session, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Acte CCAM non trouvé")
    return CCAMActResponse(**act.__dict__)


@router.put("/acts/{act_id}/validation", response_model=CCAMActResponse)
def update_ccam_act_validation(
    act_id: int,
    validation_data: CCAMActUpdate,
    session: Session = Depends(get_session)
):
    """Mettre à jour la validation d'un acte CCAM"""
    try:
        if validation_data.valide is not None:
            act = CCAMService.update_act_validation(session, act_id, validation_data.valide)
        else:
            act = CCAMService.get_act_by_id(session, act_id)
            if not act:
                raise HTTPException(status_code=404, detail="Acte CCAM non trouvé")

        return CCAMActResponse(**act.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/validate-code/{code_acte}")
def validate_ccam_code(code_acte: str, session: Session = Depends(get_session)):
    """Valider un code CCAM"""
    is_valid = CCAMService.validate_ccam_code(session, code_acte)
    return {"code_acte": code_acte, "is_valid": is_valid}


@router.get("/acts/{act_id}/modificateurs")
def get_ccam_act_modificateurs(act_id: int, session: Session = Depends(get_session)):
    """Récupérer les modificateurs d'un acte CCAM"""
    act = CCAMService.get_act_by_id(session, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Acte CCAM non trouvé")

    modificateurs = CCAMService.get_modificateurs_list(act)
    return {"act_id": act_id, "modificateurs": modificateurs}


@router.get("/acts/{act_id}/total-amount")
def get_ccam_act_total_amount(act_id: int, session: Session = Depends(get_session)):
    """Calculer le montant total d'un acte CCAM"""
    act = CCAMService.get_act_by_id(session, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Acte CCAM non trouvé")

    total = CCAMService.calculate_total_amount(act)
    return {"act_id": act_id, "total_amount": total}