"""API REST pour l'export FHIR."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from typing import Optional
from app.db import get_session
from app.models_structure_fhir import EntiteJuridique
from app.services.fhir_export_service import FHIRExportService
from app.converters.fhir_converter import FHIRBundle


router = APIRouter(prefix="/api/fhir", tags=["FHIR Export"])


@router.get("/export/structure/{ej_id}", response_model=dict)
async def export_structure(
    ej_id: int,
    session: Session = Depends(get_session)
):
    """
    Exporte la structure organisationnelle au format FHIR.
    
    Retourne un Bundle FHIR de type 'transaction' contenant toutes les
    ressources Location de la hiérarchie de l'entité juridique.
    
    Args:
        ej_id: ID de l'entité juridique à exporter
        
    Returns:
        Bundle FHIR avec les ressources Location
        
    Raises:
        404: Entité juridique non trouvée
    """
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Créer le service d'export
    fhir_url = ej.ght_context.fhir_server_url if ej.ght_context else "http://localhost:8000/fhir"
    service = FHIRExportService(session, fhir_url)
    
    # Exporter la structure
    bundle = service.export_structure(ej)
    
    return bundle.dict()


@router.get("/export/patients/{ej_id}", response_model=dict)
async def export_patients(
    ej_id: int,
    limit: Optional[int] = Query(None, description="Nombre maximum de patients à exporter"),
    offset: Optional[int] = Query(0, description="Nombre de patients à sauter"),
    session: Session = Depends(get_session)
):
    """
    Exporte les patients au format FHIR.
    
    Retourne un Bundle FHIR de type 'transaction' contenant toutes les
    ressources Patient liées à l'entité juridique.
    
    Args:
        ej_id: ID de l'entité juridique
        limit: Nombre maximum de patients à exporter (pagination)
        offset: Nombre de patients à sauter (pagination)
        
    Returns:
        Bundle FHIR avec les ressources Patient
        
    Raises:
        404: Entité juridique non trouvée
    """
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Créer le service d'export
    fhir_url = ej.ght_context.fhir_server_url if ej.ght_context else "http://localhost:8000/fhir"
    service = FHIRExportService(session, fhir_url)
    
    # Exporter les patients
    bundle = service.export_patients(ej, limit=limit, offset=offset)
    
    return bundle.dict()


@router.get("/export/venues/{ej_id}", response_model=dict)
async def export_venues(
    ej_id: int,
    limit: Optional[int] = Query(None, description="Nombre maximum de venues à exporter"),
    offset: Optional[int] = Query(0, description="Nombre de venues à sauter"),
    session: Session = Depends(get_session)
):
    """
    Exporte les venues (séjours/rencontres) au format FHIR.
    
    Retourne un Bundle FHIR de type 'transaction' contenant toutes les
    ressources Encounter liées à l'entité juridique.
    
    Args:
        ej_id: ID de l'entité juridique
        limit: Nombre maximum de venues à exporter (pagination)
        offset: Nombre de venues à sauter (pagination)
        
    Returns:
        Bundle FHIR avec les ressources Encounter
        
    Raises:
        404: Entité juridique non trouvée
    """
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Créer le service d'export
    fhir_url = ej.ght_context.fhir_server_url if ej.ght_context else "http://localhost:8000/fhir"
    service = FHIRExportService(session, fhir_url)
    
    # Exporter les venues
    bundle = service.export_venues(ej, limit=limit, offset=offset)
    
    return bundle.dict()


@router.get("/export/all/{ej_id}", response_model=dict)
async def export_all(
    ej_id: int,
    session: Session = Depends(get_session)
):
    """
    Exporte toutes les données (structure, patients, venues) au format FHIR.
    
    Retourne un dictionnaire avec trois bundles FHIR séparés.
    
    Args:
        ej_id: ID de l'entité juridique à exporter
        
    Returns:
        Dictionnaire avec les clés:
        - structure: Bundle avec les ressources Location
        - patients: Bundle avec les ressources Patient
        - venues: Bundle avec les ressources Encounter
        
    Raises:
        404: Entité juridique non trouvée
    """
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Créer le service d'export
    fhir_url = ej.ght_context.fhir_server_url if ej.ght_context else "http://localhost:8000/fhir"
    service = FHIRExportService(session, fhir_url)
    
    # Exporter toutes les données
    structure_bundle = service.export_structure(ej)
    patients_bundle = service.export_patients(ej)
    venues_bundle = service.export_venues(ej)
    
    return {
        "structure": structure_bundle.dict(),
        "patients": patients_bundle.dict(),
        "venues": venues_bundle.dict()
    }


@router.get("/export/statistics/{ej_id}", response_model=dict)
async def export_statistics(
    ej_id: int,
    session: Session = Depends(get_session)
):
    """
    Récupère les statistiques d'export pour une entité juridique.
    
    Args:
        ej_id: ID de l'entité juridique
        
    Returns:
        Dictionnaire avec les statistiques:
        - location_count: Nombre de locations
        - patient_count: Nombre de patients
        - venue_count: Nombre de venues
        
    Raises:
        404: Entité juridique non trouvée
    """
    from app.models import Patient, Venue, Dossier
    from app.models_structure import (
        EntiteGeographique, Pole, Service, UniteFonctionnelle,
        UniteHebergement, Chambre, Lit
    )
    
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Compter les locations
    eg_count = session.query(EntiteGeographique).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    pole_count = session.query(Pole).join(
        EntiteGeographique
    ).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    service_count = session.query(Service).join(
        Pole
    ).join(
        EntiteGeographique
    ).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    uf_count = session.query(UniteFonctionnelle).join(
        Service
    ).join(
        Pole
    ).join(
        EntiteGeographique
    ).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    uh_count = session.query(UniteHebergement).join(
        UniteFonctionnelle
    ).join(
        Service
    ).join(
        Pole
    ).join(
        EntiteGeographique
    ).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    chambre_count = session.query(Chambre).join(
        UniteHebergement
    ).join(
        UniteFonctionnelle
    ).join(
        Service
    ).join(
        Pole
    ).join(
        EntiteGeographique
    ).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    lit_count = session.query(Lit).join(
        Chambre
    ).join(
        UniteHebergement
    ).join(
        UniteFonctionnelle
    ).join(
        Service
    ).join(
        Pole
    ).join(
        EntiteGeographique
    ).filter(
        EntiteGeographique.entite_juridique_id == ej_id
    ).count()
    
    # Compter les patients (via dossiers liés à l'EJ)
    patient_count = session.query(Patient).join(
        Dossier
    ).filter(
        Dossier.entite_juridique_id == ej_id
    ).distinct().count()
    
    # Compter les venues (via dossiers liés à l'EJ)
    venue_count = session.query(Venue).join(
        Dossier
    ).filter(
        Dossier.entite_juridique_id == ej_id
    ).count()
    
    return {
        "entite_juridique": {
            "id": ej.id,
            "name": ej.name,
            "finess": ej.finess_ej
        },
        "locations": {
            "entites_geographiques": eg_count,
            "poles": pole_count,
            "services": service_count,
            "unites_fonctionnelles": uf_count,
            "unites_hebergement": uh_count,
            "chambres": chambre_count,
            "lits": lit_count,
            "total": eg_count + pole_count + service_count + uf_count + uh_count + chambre_count + lit_count
        },
        "patients": patient_count,
        "venues": venue_count
    }