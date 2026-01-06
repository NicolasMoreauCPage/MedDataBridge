"""
Schémas Pydantic pour la validation des données API.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class PatientBase(BaseModel):
    """Schéma de base pour un patient."""
    nom: Optional[str] = None
    prenom: Optional[str] = None
    nom_naissance: Optional[str] = None
    date_naissance: Optional[datetime] = None
    sexe: Optional[str] = None
    nir: Optional[str] = None


class PatientCreate(PatientBase):
    """Schéma pour la création d'un patient."""
    pass


class PatientUpdate(PatientBase):
    """Schéma pour la mise à jour d'un patient."""
    pass


class PatientResponse(PatientBase):
    """Schéma de réponse pour un patient."""
    id: int
    ipp: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class DossierBase(BaseModel):
    """Schéma de base pour un dossier."""
    patient_id: int
    num_dossier: Optional[str] = None
    nature_sejour: Optional[str] = None


class DossierCreate(DossierBase):
    """Schéma pour la création d'un dossier."""
    pass


class DossierUpdate(BaseModel):
    """Schéma pour la mise à jour d'un dossier."""
    nature_sejour: Optional[str] = None
    date_sortie_prevue: Optional[datetime] = None


class DossierResponse(DossierBase):
    """Schéma de réponse pour un dossier."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class VenueBase(BaseModel):
    """Schéma de base pour une venue."""
    dossier_id: int
    start_time: datetime
    venue_type: Optional[str] = None


class VenueCreate(VenueBase):
    """Schéma pour la création d'une venue."""
    pass


class VenueResponse(VenueBase):
    """Schéma de réponse pour une venue."""
    id: int
    end_time: Optional[datetime] = None
    venue_seq: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class MouvementBase(BaseModel):
    """Schéma de base pour un mouvement."""
    venue_id: int
    when: datetime
    uf_id: Optional[int] = None
    uh_id: Optional[int] = None


class MouvementCreate(MouvementBase):
    """Schéma pour la création d'un mouvement."""
    pass


class MouvementResponse(MouvementBase):
    """Schéma de réponse pour un mouvement."""
    id: int
    
    model_config = ConfigDict(from_attributes=True)
