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
def create_ucd_act(
    act: UCDActCreate,
    session: Session = Depends(get_session)
):
    """Crée un nouvel acte UCD."""
    # TODO: Implémenter avec le service UCD
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{act_id}", response_model=UCDActResponse)
def get_ucd_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Récupère un acte UCD par son ID."""
    # TODO: Implémenter avec le service UCD
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/", response_model=List[UCDActResponse])
def list_ucd_acts(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    """Liste les actes UCD."""
    # TODO: Implémenter avec le service UCD
    return []


@router.put("/{act_id}", response_model=UCDActResponse)
def update_ucd_act(
    act_id: int,
    act: UCDActUpdate,
    session: Session = Depends(get_session)
):
    """Met à jour un acte UCD."""
    # TODO: Implémenter avec le service UCD
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{act_id}")
def delete_ucd_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Supprime un acte UCD."""
    # TODO: Implémenter avec le service UCD
    raise HTTPException(status_code=501, detail="Not implemented")
