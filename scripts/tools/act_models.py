from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from sqlmodel import SQLModel, Field, Relationship

from app.models import Dossier

if TYPE_CHECKING:
    from app.models_practitioners import MedecinResponsable


class NGAPAct(SQLModel, table=True):
    """Acte NGAP - Nomenclature Générale des Actes Professionnels"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    lettre_cle: str = Field(description="Lettre-clé NGAP (A-Z)")
    coefficient: float = Field(description="Coefficient NGAP")
    execute_date: datetime = Field(description="Date d'exécution")
    prestataire_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    denombrement: Optional[int] = Field(default=None, description="Dénombrement")
    position_dentaire: Optional[str] = Field(default=None, description="Position dentaire")
    execute_heure: Optional[str] = Field(default=None, description="Heure d'exécution")
    numero_seance: Optional[int] = Field(default=None, description="Numéro de séance")
    montant: Optional[float] = Field(default=None, description="Montant en euros")
    commentaire: Optional[str] = Field(default=None, description="Commentaire")
    facturable: bool = Field(default=True, description="Acte facturable")
    valide: bool = Field(default=False, description="Acte validé")
    facture: bool = Field(default=False, description="Acte facturé")

    dossier: Dossier = Relationship(back_populates="ngap_acts")
    prestataire: Optional["MedecinResponsable"] = Relationship(back_populates="ngap_acts")


class UCDAct(SQLModel, table=True):
    """Acte UCD - Unité Commune de Dispensation"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    code_cip: str = Field(description="Code CIP-13 (13 chiffres)")
    designation: str = Field(description="Désignation du médicament")
    quantite: int = Field(description="Quantité dispensée")
    prix_unitaire: float = Field(description="Prix unitaire en euros")
    montant_total: float = Field(description="Montant total en euros")
    execute_date: datetime = Field(description="Date de dispensation")
    prestataire_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    commentaire: Optional[str] = Field(default=None, description="Commentaire")
    facturable: bool = Field(default=True, description="Acte facturable")
    valide: bool = Field(default=False, description="Acte validé")
    facture: bool = Field(default=False, description="Acte facturé")

    dossier: Dossier = Relationship(back_populates="ucd_acts")
    prestataire: Optional["MedecinResponsable"] = Relationship(back_populates="ucd_acts")


class LPPAct(SQLModel, table=True):
    """Acte LPP - Liste des Produits et Prestations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    code_lpp: str = Field(description="Code LPP (13 chiffres)")
    libelle: str = Field(description="Libellé de la prothèse")
    quantite: int = Field(default=1, description="Quantité")
    prix_unitaire: float = Field(description="Prix unitaire en euros")
    montant_total: float = Field(description="Montant total en euros")
    execute_date: datetime = Field(description="Date d'implantation")
    prestataire_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    commentaire: Optional[str] = Field(default=None, description="Commentaire")
    facturable: bool = Field(default=True, description="Acte facturable")
    valide: bool = Field(default=False, description="Acte validé")
    facture: bool = Field(default=False, description="Acte facturé")

    dossier: Dossier = Relationship(back_populates="lpp_acts")
    prestataire: Optional["MedecinResponsable"] = Relationship(back_populates="lpp_acts")


class CCAMAct(SQLModel, table=True):
    """Acte CCAM - Classification Commune des Actes Médicaux"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")

    # Code CCAM (obligatoire, format AAAA999)
    code_acte: str = Field(description="Code acte CCAM (4 lettres + 3 chiffres)")

    # Code activité (obligatoire, 2 chiffres)
    code_activite: str = Field(description="Code activité (2 chiffres)")

    # Code phase (optionnel, 2 chiffres)
    code_phase: Optional[str] = Field(default=None, description="Code phase (2 chiffres)")

    # Modificateurs (liste de codes A-Z, 0-9)
    modificateurs: str = Field(default="", description="Modificateurs séparés par des virgules")

    # Informations de réalisation
    execute_date: datetime = Field(description="Date d'exécution")
    execute_heure: Optional[str] = Field(default=None, description="Heure d'exécution (HH:MM)")

    # Quantité et tarification
    quantite: int = Field(default=1, description="Quantité")
    montant: Optional[float] = Field(default=None, description="Montant en euros")

    # Extension (optionnel, pour actes complexes)
    extension: Optional[str] = Field(default=None, description="Code extension")

    # Informations complémentaires
    commentaire: Optional[str] = Field(default=None, description="Commentaire")
    facturable: bool = Field(default=True, description="Acte facturable")
    valide: bool = Field(default=False, description="Acte validé")
    facture: bool = Field(default=False, description="Acte facturé")

    # Relations
    dossier: Dossier = Relationship(back_populates="ccam_acts")
    executant_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    executant: Optional["MedecinResponsable"] = Relationship(
        back_populates="ccam_acts_executant",
        sa_relationship_kwargs={"foreign_keys": "CCAMAct.executant_id"}
    )
    prescripteur_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    prescripteur: Optional["MedecinResponsable"] = Relationship(
        back_populates="ccam_acts_prescripteur",
        sa_relationship_kwargs={"foreign_keys": "CCAMAct.prescripteur_id"}
    )

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# --- Contrat (lié aux dossiers) ---

class Contract(SQLModel, table=True):
    """Contrat médical associé à un dossier"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    contract_type: str = Field(description="Type de contrat (NGAP, UCD, LPP, etc.)")
    contract_number: str = Field(description="Numéro de contrat")
    start_date: date = Field(description="Date de début")
    end_date: Optional[date] = Field(default=None, description="Date de fin")
    status: str = Field(default="active", description="Statut du contrat")
    description: Optional[str] = Field(default=None, description="Description")

    dossier: Dossier = Relationship(back_populates="contracts")
