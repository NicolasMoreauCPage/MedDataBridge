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
    """
    Crée un nouveau dossier pour un patient.
    
    Crée un dossier avec numéro de séquence auto-généré et le relie au patient
    et à l'entité juridique spécifiés.
    
    Args:
        patient_id: ID du patient propriétaire du dossier
        ej_id: ID de l'entité juridique (hôpital/clinique)
        dossier_type: Type de dossier (HOSPITALISE, EXTERNE, URGENCE)
        admit_time: Date/heure d'admission (datetime.now() par défaut)
        session: Session DB injectée automatiquement
        
    Returns:
        Dossier: Le dossier créé avec son ID et numéro de séquence
        
    Raises:
        HTTPException 404: Patient non trouvé
        
    Example:
        ```
        POST /api/dossiers?patient_id=123&ej_id=1&dossier_type=HOSPITALISE
        ```
    """
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
    """
    Récupère les détails complets d'un dossier par son ID.
    
    Args:
        dossier_id: Identifiant unique du dossier
        session: Session DB injectée automatiquement
        
    Returns:
        Dossier: Données complètes du dossier (type, dates, patient_id, ej_id, etc.)
        
    Raises:
        HTTPException 404: Dossier non trouvé
        
    Example:
        ```
        GET /api/dossiers/456
        ```
    """
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
    """
    Liste les dossiers avec pagination et filtres multiples.
    
    Résultats triés par date de début décroissante (plus récents en premier).
    
    Args:
        skip: Nombre d'éléments à sauter (pagination)
        limit: Nombre maximum de résultats (1-1000)
        patient_id: Filtre par patient
        dossier_type: Filtre par type (HOSPITALISE, EXTERNE, URGENCE)
        ej_id: Filtre par entité juridique
        date_start: Filtre dossiers avec date_start >= date_start
        date_end: Filtre dossiers avec date_end <= date_end
        session: Session DB injectée automatiquement
        
    Returns:
        List[Dossier]: Liste des dossiers correspondant aux critères
        
    Example:
        ```
        GET /api/dossiers?patient_id=123&limit=10
        GET /api/dossiers?ej_id=1&dossier_type=HOSPITALISE&date_start=2025-01-01
        ```
    """
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
    """
    Met à jour les données d'un dossier existant.
    
    Seuls les champs fournis sont mis à jour. L'ID ne peut pas être modifié.
    
    Args:
        dossier_id: ID du dossier à mettre à jour
        dossier_update: Nouvelles données (champs optionnels)
        session: Session DB injectée automatiquement
        
    Returns:
        Dossier: Le dossier mis à jour
        
    Raises:
        HTTPException 404: Dossier non trouvé
        
    Example:
        ```json
        PUT /api/dossiers/456
        {
            "dossier_type": "EXTERNE",
            "date_end": "2026-01-10T14:30:00"
        }
        ```
    """
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
    """
    Supprime un dossier de la base de données.
    
    ⚠️ Attention: Opération irréversible. Les venues et mouvements associés
    seront également supprimés (cascade).
    
    Args:
        dossier_id: ID du dossier à supprimer
        session: Session DB injectée automatiquement
        
    Returns:
        Status 204 No Content si succès
        
    Raises:
        HTTPException 404: Dossier non trouvé
        
    Example:
        ```
        DELETE /api/dossiers/456
        ```
    """
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
    """
    Récupère toutes les venues (séjours en unité) d'un dossier.
    
    Retourne l'historique des passages du patient dans les différentes unités
    fonctionnelles durant son séjour.
    
    Args:
        dossier_id: ID du dossier
        session: Session DB injectée automatiquement
        
    Returns:
        List[Venue]: Liste de toutes les venues du dossier
        
    Raises:
        HTTPException 404: Dossier non trouvé
        
    Example:
        ```
        GET /api/dossiers/456/venues
        ```
    """
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
    """
    Récupère tous les mouvements d'un dossier triés chronologiquement.
    
    Retourne l'historique complet des mouvements (admissions, transferts, sorties)
    du patient pour ce dossier, triés par date croissante.
    
    Args:
        dossier_id: ID du dossier
        session: Session DB injectée automatiquement
        
    Returns:
        List[Mouvement]: Liste des mouvements triés par mouv_date
        
    Raises:
        HTTPException 404: Dossier non trouvé
        
    Example:
        ```
        GET /api/dossiers/456/mouvements
        ```
    """
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
    """
    Clôture un dossier en définissant sa date de fin.
    
    Marque la fin du séjour/dossier. Si date_end n'est pas fournie,
    utilise datetime.now() comme date de clôture.
    
    Args:
        dossier_id: ID du dossier à clôturer
        date_end: Date/heure de clôture (datetime.now() par défaut)
        session: Session DB injectée automatiquement
        
    Returns:
        Dossier: Le dossier clôturé avec date_end renseignée
        
    Raises:
        HTTPException 404: Dossier non trouvé
        HTTPException 400: Dossier déjà clôturé
        
    Example:
        ```
        POST /api/dossiers/456/close
        POST /api/dossiers/456/close?date_end=2026-01-06T15:30:00
        ```
    """
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
