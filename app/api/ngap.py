# app/api/ngap.py
"""
API endpoints pour la gestion des actes NGAP
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.db import get_session
from app.models import NGAPAct, Dossier
from app.models_practitioners import MedecinResponsable

from app.services.ngap_service import NGAPService, NGAPActCreate, NGAPActResponse

router = APIRouter(prefix="/api/ngap", tags=["NGAP"])


@router.post("/", response_model=NGAPActResponse)
async def create_ngap_act(act: NGAPActCreate, db: Session = Depends(get_session)):
    """Créer un nouvel acte NGAP"""
    service = NGAPService(db)
    return service.create_act(act)


@router.get("/dossier/{dossier_id}", response_model=List[NGAPActResponse])
async def get_ngap_acts_by_dossier(dossier_id: int, db: Session = Depends(get_session)):
    """Récupérer les actes NGAP d'un dossier"""
    service = NGAPService(db)
    return service.get_acts_by_dossier(dossier_id)


@router.put("/{act_id}", response_model=NGAPActResponse)
async def update_ngap_act(act_id: int, act: NGAPActCreate, db: Session = Depends(get_session)):
    """Mettre à jour un acte NGAP"""
    service = NGAPService(db)
    return service.update_act(act_id, act)


@router.delete("/{act_id}")
async def delete_ngap_act(act_id: int, db: Session = Depends(get_session)):
    """Supprimer un acte NGAP"""
    service = NGAPService(db)
    service.delete_act(act_id)
    return {"message": "Acte NGAP supprimé"}


@router.post("/{act_id}/validate")
async def validate_ngap_act(act_id: int, db: Session = Depends(get_session)):
    """Valider un acte NGAP"""
    service = NGAPService(db)
    return service.validate_act(act_id)