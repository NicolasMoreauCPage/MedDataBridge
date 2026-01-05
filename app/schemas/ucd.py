"""
Schémas Pydantic pour UCD (Unité Commune de Dispensation).
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class UCDActBase(BaseModel):
    """Schéma de base pour un acte UCD."""
    code: str
    libelle: Optional[str] = None
    quantite: Optional[float] = 1.0
    dossier_id: Optional[int] = None


class UCDActCreate(UCDActBase):
    """Schéma pour la création d'un acte UCD."""
    pass


class UCDActUpdate(BaseModel):
    """Schéma pour la mise à jour d'un acte UCD."""
    code: Optional[str] = None
    libelle: Optional[str] = None
    quantite: Optional[float] = None


class UCDActResponse(UCDActBase):
    """Schéma de réponse pour un acte UCD."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
