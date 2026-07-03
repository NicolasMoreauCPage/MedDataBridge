"""
Schémas Pydantic pour LPP (Liste des Produits et Prestations).

Les noms de champs suivent ceux du modèle SQLModel `app.models.LPPAct`
(conforme HPRIM XML v2.4) pour éviter toute dérive entre l'API et la
persistance.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class LPPActBase(BaseModel):
    """Schéma de base pour un acte LPP."""
    dossier_id: int
    code_lpp: str
    denomination_libelle: Optional[str] = None
    execute_date: datetime
    quantite: int = 1
    montant_unitaire_facture_ttc: float
    prestataire_id: Optional[int] = None
    commentaire: Optional[str] = None


class LPPActCreate(LPPActBase):
    """Schéma pour la création d'un acte LPP."""
    pass


class LPPActUpdate(BaseModel):
    """Schéma pour la mise à jour d'un acte LPP."""
    code_lpp: Optional[str] = None
    denomination_libelle: Optional[str] = None
    execute_date: Optional[datetime] = None
    quantite: Optional[int] = None
    montant_unitaire_facture_ttc: Optional[float] = None
    prestataire_id: Optional[int] = None
    commentaire: Optional[str] = None


class LPPActResponse(LPPActBase):
    """Schéma de réponse pour un acte LPP."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
