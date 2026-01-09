"""
API routers for HPRIM interventions and cotations management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List, Optional
from datetime import datetime

from app.db_session_factory import get_session
from app.services.hprim_intervention_service import HprimInterventionService
from app.hprim_models import HprimIntervention

router = APIRouter(prefix="/api/hprim/interventions", tags=["HPRIM Interventions"])


@router.get("/{dossier_id}/cotations-count")
async def get_dossier_cotations_count(
    dossier_id: int,
    session: Session = Depends(get_session)
) -> dict:
    """
    Récupère le nombre de cotations d'un dossier
    
    Utilisé pour afficher le badge "Voir les cotations" dans l'IHM
    """
    try:
        service = HprimInterventionService(session)
        count = await service.get_dossier_cotations_count(dossier_id)
        
        return {
            "dossier_id": dossier_id,
            "cotations_count": count,
            "has_cotations": count > 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{dossier_id}")
async def list_interventions(
    dossier_id: int,
    session: Session = Depends(get_session)
) -> dict:
    """
    Liste toutes les interventions d'un dossier
    """
    try:
        service = HprimInterventionService(session)
        interventions = await service.get_interventions_for_dossier(dossier_id)
        
        return {
            "dossier_id": dossier_id,
            "interventions": interventions,
            "count": len(interventions)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{intervention_id}/cotations")
async def get_intervention_cotations(
    intervention_id: str,
    session: Session = Depends(get_session)
) -> dict:
    """
    Récupère toutes les cotations d'une intervention
    """
    try:
        service = HprimInterventionService(session)
        cotations = await service.get_cotations_for_intervention(intervention_id)
        
        return {
            "intervention_id": intervention_id,
            "cotations": [
                {
                    "cotation_id": c.cotation_id,
                    "actes_ccam": len(c.actes_ccam),
                    "actes_ngap": len(c.actes_ngap),
                    "statut": c.statut,
                    "date_creation": c.date_creation.isoformat(),
                }
                for c in cotations
            ],
            "count": len(cotations)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{dossier_id}/update-cotations-flags")
async def update_cotations_flags(
    dossier_id: int,
    session: Session = Depends(get_session)
) -> dict:
    """
    Met à jour les flags has_cotations et cotations_count du dossier
    
    Endpoint interne appelé lors de modifications des cotations
    """
    try:
        service = HprimInterventionService(session)
        success = await service.update_dossier_cotations_flags(dossier_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dossier {dossier_id} not found"
            )
        
        return {
            "status": "success",
            "dossier_id": dossier_id,
            "message": "Cotations flags updated"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
