"""
API REST pour la gestion des actes LPP (Liste des Produits et Prestations).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.db import get_session
from app.schemas.lpp import LPPActCreate, LPPActUpdate, LPPActResponse
from app.services.lpp_service import LPPService

router = APIRouter(prefix="/lpp", tags=["LPP API"])


@router.post("/", response_model=LPPActResponse)
async def create_lpp_act(
    act: LPPActCreate,
    session: Session = Depends(get_session)
):
    """Crée un nouvel acte LPP."""
    service = LPPService(session)
    return await service.create_act(act)


@router.get("/{act_id}", response_model=LPPActResponse)
async def get_lpp_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Récupère un acte LPP par son ID."""
    service = LPPService(session)
    return await service.get_act_by_id(act_id)


@router.get("/dossier/{dossier_id}", response_model=List[LPPActResponse])
async def list_lpp_acts_by_dossier(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Liste les actes LPP d'un dossier."""
    service = LPPService(session)
    return await service.get_acts_by_dossier(dossier_id)


@router.put("/{act_id}", response_model=LPPActResponse)
async def update_lpp_act(
    act_id: int,
    act: LPPActUpdate,
    session: Session = Depends(get_session)
):
    """Met à jour un acte LPP."""
    service = LPPService(session)
    return await service.update_act(act_id, act)


@router.delete("/{act_id}")
async def delete_lpp_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Supprime un acte LPP."""
    service = LPPService(session)
    await service.delete_act(act_id)
    return {"message": "Acte LPP supprimé avec succès"}


@router.post("/{act_id}/validate", response_model=LPPActResponse)
async def validate_lpp_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Valide un acte LPP."""
    service = LPPService(session)
    return await service.validate_act(act_id)
