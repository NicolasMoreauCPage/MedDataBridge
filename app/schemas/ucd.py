"""
Schémas Pydantic pour UCD (Unité Commune de Dispensation).

Les noms de champs suivent ceux du modèle SQLModel `app.models.UCDAct`
(conforme HPRIM XML v2.4) pour éviter toute dérive entre l'API et la
persistance.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class UCDActBase(BaseModel):
    """Schéma de base pour un acte UCD."""
    dossier_id: int
    code_ucd: str
    denomination_libelle: Optional[str] = None
    execute_date: datetime
    quantite: float = 1.0
    montant_unitaire_facture_ttc: Optional[float] = None
    prestataire_id: Optional[int] = None
    commentaire: Optional[str] = None


class UCDActCreate(UCDActBase):
    """Schéma pour la création d'un acte UCD."""
    pass


class UCDActUpdate(BaseModel):
    """Schéma pour la mise à jour d'un acte UCD."""
    code_ucd: Optional[str] = None
    denomination_libelle: Optional[str] = None
    execute_date: Optional[datetime] = None
    quantite: Optional[float] = None
    montant_unitaire_facture_ttc: Optional[float] = None
    prestataire_id: Optional[int] = None
    commentaire: Optional[str] = None


class UCDActResponse(UCDActBase):
    """Schéma de réponse pour un acte UCD."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
