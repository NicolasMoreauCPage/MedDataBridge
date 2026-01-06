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
    """
    Crée un nouvel acte LPP (Liste Produits et Prestations).
    
    Les LPP représentent des dispositifs médicaux, prothèses, orthèses, etc.
    identifiés par leur code LPP (13 chiffres). La validation automatique vérifie:
    - Format code LPP (13 chiffres)
    - Quantité > 0
    - Prix unitaire > 0
    - Cohérence prix total = prix unitaire * quantité
    
    Args:
        act: Données de l'acte (dossier_id, code_lpp, quantité, prix)
        session: Session DB injectée automatiquement
        
    Returns:
        LPPActResponse: L'acte créé avec son ID
        
    Raises:
        HTTPException 400: Validation échouée (code LPP invalide, prix négatif, etc.)
        
    Example:
        ```json
        POST /lpp/
        {
            "dossier_id": 123,
            "code_lpp": "2109876543210",
            "quantity": 1,
            "unit_price": 450.00,
            "total_price": 450.00
        }
        ```
    """
    service = LPPService(session)
    return await service.create_act(act)


@router.get("/{act_id}", response_model=LPPActResponse)
async def get_lpp_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """
    Récupère un acte LPP par son ID.
    
    Args:
        act_id: Identifiant unique de l'acte LPP
        session: Session DB injectée automatiquement
        
    Returns:
        LPPActResponse: Détails complets de l'acte
        
    Raises:
        HTTPException 404: Acte non trouvé
    """
    service = LPPService(session)
    return await service.get_act_by_id(act_id)


@router.get("/dossier/{dossier_id}", response_model=List[LPPActResponse])
async def list_lpp_acts_by_dossier(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """
    Liste tous les actes LPP d'un dossier patient.
    
    Utile pour obtenir l'historique des dispositifs médicaux, prothèses,
    orthèses dispensés durant un séjour.
    
    Args:
        dossier_id: ID du dossier patient
        session: Session DB injectée automatiquement
        
    Returns:
        List[LPPActResponse]: Liste de tous les actes LPP du dossier
    """
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
    """
    Valide un acte LPP selon les règles métier.
    
    Vérifie:
    - Format code LPP (13 chiffres)
    - Quantité > 0
    - Prix unitaire > 0
    - Cohérence total = unitaire * quantité (±0.01€ tolérance)
    
    Args:
        act_id: ID de l'acte à valider
        session: Session DB injectée automatiquement
        
    Returns:
        LPPActResponse: L'acte validé
        
    Raises:
        HTTPException 404: Acte non trouvé
        HTTPException 400: Validation échouée
    """
    service = LPPService(session)
    return await service.validate_act(act_id)
