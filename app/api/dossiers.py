"""
API REST pour la gestion des dossiers.
Utilise directement le model Dossier de SQLModel.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.db import get_session
from app.models import Dossier, Patient, Venue, Mouvement, DossierType

router = APIRouter(prefix="/api/dossiers", tags=["Dossiers API"])


@router.post("/", status_code=201)
async def create_dossier(
    patient_id: int,
    ej_id: int,
    dossier_type: DossierType = DossierType.HOSPITALISE,
    admit_time: Optional[datetime] = None,
    session: Session = Depends(get_session)
):
    """Crée un nouveau dossier."""
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    
    from app.services import dossiers_service
    dossier = dossiers_service.create_dossier(
        session=session,
        patient_id=patient_id,
        ej_id=ej_id,
        dossier_type=dossier_type,
        admit_time=admit_time
    )
    return dossier


@router.get("/{dossier_id}", response_model=Dossier)
async def get_dossier(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Récupère un dossier par son ID."""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    return dossier


@router.get("/", response_model=List[Dossier])
async def list_dossiers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
    dossier_type: Optional[str] = None,
    ej_id: Optional[int] = None,
    date_start: Optional[datetime] = None,
    date_end: Optional[datetime] = None,
    session: Session = Depends(get_session)
):
    """Liste les dossiers avec pagination et filtres."""
    query = select(Dossier)
    
    if patient_id:
        query = query.where(Dossier.patient_id == patient_id)
    if dossier_type:
        query = query.where(Dossier.dossier_type == dossier_type)
    if ej_id:
        query = query.where(Dossier.ej_id == ej_id)
    if date_start:
        query = query.where(Dossier.date_start >= date_start)
    if date_end:
        query = query.where(Dossier.date_end <= date_end)
    
    query = query.order_by(Dossier.date_start.desc()).offset(skip).limit(limit)
    return session.exec(query).all()


@router.put("/{dossier_id}", response_model=Dossier)
async def update_dossier(
    dossier_id: int,
    dossier_update: Dossier,
    session: Session = Depends(get_session)
):
    """Met à jour un dossier existant."""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    update_data = dossier_update.model_dump(exclude_unset=True, exclude={"id"})
    for field, value in update_data.items():
        setattr(dossier, field, value)
    
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier


@router.delete("/{dossier_id}", status_code=204)
async def delete_dossier(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Supprime un dossier."""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    session.delete(dossier)
    session.commit()


@router.get("/{dossier_id}/venues")
async def get_dossier_venues(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Récupère les venues d'un dossier."""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    query = select(Venue).where(Venue.dossier_id == dossier_id)
    return session.exec(query).all()


@router.get("/{dossier_id}/mouvements")
async def get_dossier_mouvements(
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Récupère les mouvements d'un dossier."""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    query = select(Mouvement).where(Mouvement.dossier_id == dossier_id).order_by(Mouvement.mouv_date)
    return session.exec(query).all()


@router.post("/{dossier_id}/close")
async def close_dossier(
    dossier_id: int,
    date_end: Optional[datetime] = None,
    session: Session = Depends(get_session)
):
    """Clôture un dossier."""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    if dossier.date_end:
        raise HTTPException(status_code=400, detail="Dossier déjà clôturé")
    
    dossier.date_end = date_end or datetime.now()
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier
