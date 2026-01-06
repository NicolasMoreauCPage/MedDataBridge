"""
API REST pour la gestion des actes UCD (Unité Commune de Dispensation).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.db import get_session
from app.schemas.ucd import UCDActCreate, UCDActUpdate, UCDActResponse
from app.services.ucd_service import UCDService

router = APIRouter(prefix="/ucd", tags=["UCD API"])


@router.post("/", response_model=UCDActResponse)
async def create_ucd_act(
    act: UCDActCreate,
    session: Session = Depends(get_session)
):
    """Crée un nouvel acte UCD."""
    service = UCDService(session)
    return await service.create_act(act)


@router.get("/{act_id}", response_model=UCDActResponse)
async def get_ucd_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Récupère un acte UCD par son ID."""
    service = UCDService(session)
    return await service.get_act_by_id(act_id)


@router.get("/dossier/{dossier_id}", response_model=List[UCDActResponse])
async def list_ucd_acts_by_dossier(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Liste les actes UCD d'un dossier."""
    service = UCDService(session)
    return await service.get_acts_by_dossier(dossier_id)


@router.put("/{act_id}", response_model=UCDActResponse)
async def update_ucd_act(
    act_id: int,
    act: UCDActUpdate,
    session: Session = Depends(get_session)
):
    """Met à jour un acte UCD."""
    service = UCDService(session)
    return await service.update_act(act_id, act)


@router.delete("/{act_id}")
async def delete_ucd_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Supprime un acte UCD."""
    service = UCDService(session)
    await service.delete_act(act_id)
    return {"message": "Acte UCD supprimé avec succès"}


@router.post("/{act_id}/validate", response_model=UCDActResponse)
async def validate_ucd_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Valide un acte UCD."""
    service = UCDService(session)
    return await service.validate_act(act_id)
