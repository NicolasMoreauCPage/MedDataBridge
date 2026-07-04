"""
API routers for HPRIM interventions and cotations management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session
from typing import List, Optional
from datetime import datetime

from app.db_session_factory import get_session
from app.services.hprim_intervention_service import HprimInterventionService

router = APIRouter(prefix="/api/hprim/interventions", tags=["HPRIM Interventions"])


class InterventionCreate(BaseModel):
    identifiant: str
    libelle: str
    date_intervention: datetime
    venue_id: Optional[str] = None
    lieu_execution: Optional[str] = None
    statut: str = "en_cours"


def _intervention_to_dict(intervention) -> dict:
    return {
        "id": intervention.id,
        "dossier_id": intervention.dossier_id,
        "identifiant": intervention.identifiant,
        "libelle": intervention.libelle,
        "date_intervention": intervention.date_intervention.isoformat(),
        "venue_id": intervention.venue_id,
        "lieu_execution": intervention.lieu_execution,
        "statut": intervention.statut,
        "created_at": intervention.created_at.isoformat(),
        "updated_at": intervention.updated_at.isoformat(),
    }


@router.post("/{dossier_id}")
async def create_intervention(
    dossier_id: int,
    payload: InterventionCreate,
    session: Session = Depends(get_session)
) -> dict:
    """
    Crée une intervention rattachée à un dossier.
    """
    try:
        service = HprimInterventionService(session)
        intervention = await service.create_intervention(dossier_id=dossier_id, **payload.model_dump())
        return _intervention_to_dict(intervention)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
            "interventions": [_intervention_to_dict(i) for i in interventions],
            "count": len(interventions)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{intervention_id}/cotations")
async def get_intervention_cotations(
    intervention_id: int,
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
