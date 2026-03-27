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
from app.services.patients_service import PatientCreateSchema, create_patient

router = APIRouter(prefix="/api/patients", tags=["Patients API"])


@router.post("/", response_model=Patient, status_code=201)
async def create_patient_endpoint(
    patient: PatientCreateSchema,
    session: Session = Depends(get_session)
):
    """
    Crée un nouveau patient dans la base de données.
    
    Args:
        patient: Données du patient (family, given, birth_date, gender, etc.)
        session: Session DB injectée automatiquement
        
    Returns:
        Patient: Le patient créé avec son ID généré
        
    Example:
        ```json
        POST /api/patients
        {
            "family": "DUPONT",
            "given": "Jean",
            "birth_date": "1980-05-15",
            "gender": "M"
        }
        ```
    """
    try:
        new_patient = create_patient(session, patient)
        return new_patient
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du patient: {str(e)}")


@router.get("/{patient_id}", response_model=Patient)
async def get_patient(
    patient_id: int,
    session: Session = Depends(get_session)
):
    """
    Récupère les détails complets d'un patient par son ID.
    
    Args:
        patient_id: Identifiant unique du patient
        session: Session DB injectée automatiquement
        
    Returns:
        Patient: Données complètes du patient
        
    Raises:
        HTTPException 404: Patient non trouvé
        
    Example:
        ```
        GET /api/patients/123
        ```
    """
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
    """
    Liste les patients avec pagination et filtres optionnels.
    
    Args:
        skip: Nombre d'éléments à sauter (pagination)
        limit: Nombre maximum de résultats (1-1000)
        family: Filtre sur nom de famille (recherche partielle insensible à la casse)
        given: Filtre sur prénom (recherche partielle insensible à la casse)
        birth_date: Filtre sur date de naissance exacte
        gender: Filtre sur sexe (M/F/U)
        session: Session DB injectée automatiquement
        
    Returns:
        List[Patient]: Liste des patients correspondant aux critères
        
    Example:
        ```
        GET /api/patients?family=DUPONT&limit=10
        GET /api/patients?birth_date=1980-05-15&gender=M
        ```
    """
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
    """
    Met à jour les données d'un patient existant.
    
    Seuls les champs fournis dans le corps de la requête seront mis à jour.
    L'ID du patient ne peut pas être modifié.
    
    Args:
        patient_id: ID du patient à mettre à jour
        patient_update: Nouvelles données (champs optionnels)
        session: Session DB injectée automatiquement
        
    Returns:
        Patient: Le patient mis à jour
        
    Raises:
        HTTPException 404: Patient non trouvé
        
    Example:
        ```json
        PUT /api/patients/123
        {
            "family": "MARTIN",
            "phone": "+33612345678"
        }
        ```
    """
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
    """
    Supprime un patient de la base de données.
    
    ⚠️ Attention: Cette opération est irréversible.
    Tous les dossiers associés seront potentiellement orphelins.
    
    Args:
        patient_id: ID du patient à supprimer
        session: Session DB injectée automatiquement
        
    Returns:
        Status 204 No Content si succès
        
    Raises:
        HTTPException 404: Patient non trouvé
        
    Example:
        ```
        DELETE /api/patients/123
        ```
    """
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
    """
    Récupère tous les dossiers associés à un patient.
    
    Retourne l'historique complet des hospitalisations, consultations et urgences
    du patient identifié.
    
    Args:
        patient_id: ID du patient
        session: Session DB injectée automatiquement
        
    Returns:
        List[Dossier]: Liste de tous les dossiers du patient
        
    Raises:
        HTTPException 404: Patient non trouvé
        
    Example:
        ```
        GET /api/patients/123/dossiers
        ```
    """
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
    """
    Fusionne deux fiches patient (dédoublonnage).
    
    Transfère tous les dossiers du patient source (other_id) vers le patient cible
    (patient_id), puis supprime le patient source. Utile pour corriger les doublons.
    
    Args:
        patient_id: ID du patient cible (celui qui sera conservé)
        other_id: ID du patient source (à fusionner et supprimer)
        session: Session DB injectée automatiquement
        
    Returns:
        dict: Message de confirmation et nombre de dossiers déplacés
            - message: Description de l'opération
            - moved_dossiers: Nombre de dossiers transférés
        
    Raises:
        HTTPException 404: Un des deux patients n'existe pas
        
    Example:
        ```
        POST /api/patients/123/merge/456
        Response: {
            "message": "Patient 456 fusionné dans 123",
            "moved_dossiers": 3
        }
        ```
    """
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
