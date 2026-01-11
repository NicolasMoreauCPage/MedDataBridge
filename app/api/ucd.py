"""
API REST pour la gestion des actes UCD (Unité Commune de Dispensation).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.db import get_session
from app.schemas.ucd import UCDActCreate, UCDActUpdate, UCDActResponse
from app.services.ucd_service import UCDService

router = APIRouter(prefix="/api/ucd", tags=["UCD API"])


@router.post("/", response_model=UCDActResponse, status_code=201)
async def create_ucd_act(
    act: UCDActCreate,
    session: Session = Depends(get_session)
):
    """
    Crée un nouvel acte UCD (Unité Commune de Dispensation).
    
    Les UCD représentent des médicaments ou dispositifs médicaux dispensés,
    identifiés par leur code CIP-13. La validation automatique vérifie:
    - Format CIP-13 (13 chiffres)
    - Quantité > 0
    - Prix unitaire > 0
    - Cohérence prix total = prix unitaire * quantité
    
    Args:
        act: Données de l'acte (dossier_id, code_cip, quantité, prix)
        session: Session DB injectée automatiquement
        
    Returns:
        UCDActResponse: L'acte créé avec son ID
        
    Raises:
        HTTPException 400: Validation échouée (code CIP invalide, prix négatif, etc.)
        
    Example:
        ```json
        POST /ucd/
        {
            "dossier_id": 123,
            "code_cip": "3400936396258",
            "quantity": 2,
            "unit_price": 15.50,
            "total_price": 31.00
        }
        ```
    """
    service = UCDService(session)
    return await service.create_act(act)


@router.get("/{act_id}", response_model=UCDActResponse)
async def get_ucd_act(
    act_id: int,
    session: Session = Depends(get_session)
):
    """
    Récupère un acte UCD par son ID.
    
    Args:
        act_id: Identifiant unique de l'acte UCD
        session: Session DB injectée automatiquement
        
    Returns:
        UCDActResponse: Détails complets de l'acte
        
    Raises:
        HTTPException 404: Acte non trouvé
    """
    service = UCDService(session)
    return await service.get_act_by_id(act_id)


@router.get("/dossier/{dossier_id}", response_model=List[UCDActResponse])
async def list_ucd_acts_by_dossier(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """
    Liste tous les actes UCD d'un dossier patient.
    
    Utile pour obtenir l'historique des médicaments/dispositifs dispensés
    durant un séjour.
    
    Args:
        dossier_id: ID du dossier patient
        session: Session DB injectée automatiquement
        
    Returns:
        List[UCDActResponse]: Liste de tous les actes UCD du dossier
    """
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


@router.delete("/{act_id}", status_code=204)
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
    """
    Valide un acte UCD selon les règles métier.
    
    Vérifie:
    - Format code CIP-13 (13 chiffres)
    - Quantité > 0
    - Prix unitaire > 0  
    - Cohérence total = unitaire * quantité (±0.01€ tolérance)
    
    Args:
        act_id: ID de l'acte à valider
        session: Session DB injectée automatiquement
        
    Returns:
        UCDActResponse: L'acte validé
        
    Raises:
        HTTPException 404: Acte non trouvé
        HTTPException 400: Validation échouée
    """
    service = UCDService(session)
    return await service.validate_act(act_id)
