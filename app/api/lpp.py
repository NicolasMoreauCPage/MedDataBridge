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
def create_lpp_act(
    act: LPPActCreate,
    session: Session = Depends(get_session)
):
    """Crée un nouvel acte LPP."""
    # TODO: Implémenter avec le service LPP
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{act_id}", response_model=LPPActResponse)
def get_lpp_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Récupère un acte LPP par son ID."""
    # TODO: Implémenter avec le service LPP
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/", response_model=List[LPPActResponse])
def list_lpp_acts(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    """Liste les actes LPP."""
    # TODO: Implémenter avec le service LPP
    return []


@router.put("/{act_id}", response_model=LPPActResponse)
def update_lpp_act(
    act_id: int,
    act: LPPActUpdate,
    session: Session = Depends(get_session)
):
    """Met à jour un acte LPP."""
    # TODO: Implémenter avec le service LPP
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{act_id}")
def delete_lpp_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """Supprime un acte LPP."""
    # TODO: Implémenter avec le service LPP
    raise HTTPException(status_code=501, detail="Not implemented")
