"""
API routers for HPRIM acquittements (acknowledgments) management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import Dict, Any

from app.db_session_factory import get_session
from app.services.hprim_acquittement_service import HprimAcquittementService

router = APIRouter(prefix="/api/hprim/acquittements", tags=["HPRIM Acquittements"])


@router.post("/process")
async def process_acquittement(
    acquittement_data: Dict[str, Any],
    session: Session = Depends(get_session)
) -> dict:
    """
    Traite un message d'acquittement reçu du serveur HPRIM
    
    Conformément à la spec msgAcquittementsServeurActes2_4.xsd
    """
    try:
        service = HprimAcquittementService(session)
        acquittement = await service.process_acquittement(acquittement_data)
        
        if not acquittement:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process acquittement"
            )
        
        return {
            "status": "success",
            "message_id_original": acquittement.message_id_original,
            "statut": acquittement.statut,
            "date_acquittement": acquittement.date_acquittement.isoformat(),
            "reponses_count": {
                "actes": len(acquittement.reponses_actes),
                "interventions": len(acquittement.reponses_interventions),
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{message_id}/status")
async def get_acquittement_status(
    message_id: str,
    session: Session = Depends(get_session)
) -> dict:
    """
    Récupère le statut d'un acquittement par son ID de message original
    """
    try:
        service = HprimAcquittementService(session)
        status_summary = await service.get_acquittement_status_summary(message_id)
        
        if not status_summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No acquittement found for message {message_id}"
            )
        
        return status_summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/")
async def list_recent_acquittements(
    limit: int = 50,
    session: Session = Depends(get_session)
) -> dict:
    """
    Liste les acquittements récents
    
    TODO: Implémenter quand la table sera créée
    """
    return {
        "message": "Not implemented yet - waiting for hprim_acquittement table",
        "acquittements": [],
        "count": 0
    }
