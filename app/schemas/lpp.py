"""
Schémas Pydantic pour LPP (Liste des Produits et Prestations).
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class LPPActBase(BaseModel):
    """Schéma de base pour un acte LPP."""
    code: str
    libelle: Optional[str] = None
    quantite: Optional[float] = 1.0
    prix_unitaire: Optional[float] = None
    dossier_id: Optional[int] = None


class LPPActCreate(LPPActBase):
    """Schéma pour la création d'un acte LPP."""
    pass


class LPPActUpdate(BaseModel):
    """Schéma pour la mise à jour d'un acte LPP."""
    code: Optional[str] = None
    libelle: Optional[str] = None
    quantite: Optional[float] = None
    prix_unitaire: Optional[float] = None


class LPPActResponse(LPPActBase):
    """Schéma de réponse pour un acte LPP."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
