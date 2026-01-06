"""
API REST pour la gestion des patients.
Utilise directement le model Patient de SQLModel.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import date
from app.db import get_session
from app.models import Patient, Dossier

router = APIRouter(prefix="/api/patients", tags=["Patients API"])


@router.post("/", response_model=Patient, status_code=201)
async def create_patient(
    patient: Patient,
    session: Session = Depends(get_session)
):
    """Crée un nouveau patient."""
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=Patient)
async def get_patient(
    patient_id: int,
    session: Session = Depends(get_session)
):
    """Récupère un patient par son ID."""
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    return patient


@router.get("/", response_model=List[Patient])
async def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    family: Optional[str] = None,
    given: Optional[str] = None,
    birth_date: Optional[date] = None,
    gender: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Liste les patients avec pagination et filtres."""
    query = select(Patient)
    
    if family:
        query = query.where(Patient.family.ilike(f"%{family}%"))
    if given:
        query = query.where(Patient.given.ilike(f"%{given}%"))
    if birth_date:
        query = query.where(Patient.birth_date == birth_date)
    if gender:
        query = query.where(Patient.gender == gender)
    
    query = query.offset(skip).limit(limit)
    return session.exec(query).all()


@router.put("/{patient_id}", response_model=Patient)
async def update_patient(
    patient_id: int,
    patient_update: Patient,
    session: Session = Depends(get_session)
):
    """Met à jour un patient existant."""
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    
    update_data = patient_update.model_dump(exclude_unset=True, exclude={"id"})
    for field, value in update_data.items():
        setattr(patient, field, value)
    
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(
    patient_id: int,
    session: Session = Depends(get_session)
):
    """Supprime un patient."""
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    
    session.delete(patient)
    session.commit()


@router.get("/{patient_id}/dossiers")
async def get_patient_dossiers(
    patient_id: int,
    session: Session = Depends(get_session)
):
    """Récupère les dossiers d'un patient."""
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    
    query = select(Dossier).where(Dossier.patient_id == patient_id)
    return session.exec(query).all()


@router.post("/{patient_id}/merge/{other_id}")
async def merge_patients(
    patient_id: int,
    other_id: int,
    session: Session = Depends(get_session)
):
    """Fusionne deux patients (other_id -> patient_id)."""
    patient = session.get(Patient, patient_id)
    other = session.get(Patient, other_id)
    
    if not patient or not other:
        raise HTTPException(status_code=404, detail="Un des patients n'existe pas")
    
    # Transférer les dossiers
    query = select(Dossier).where(Dossier.patient_id == other_id)
    dossiers = session.exec(query).all()
    for dossier in dossiers:
        dossier.patient_id = patient_id
        session.add(dossier)
    
    # Supprimer l'ancien patient
    session.delete(other)
    session.commit()
    
    return {"message": f"Patient {other_id} fusionné dans {patient_id}", "moved_dossiers": len(dossiers)}
