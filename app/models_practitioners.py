"""
Modèles pour les praticiens/médecins responsables

Les médecins responsables sont associés aux Unités Fonctionnelles (UF)
et peuvent être liés aux dossiers et mouvements.
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models import UniteFonctionnelle, Dossier, Mouvement


class MedecinResponsable(SQLModel, table=True):
    """
    Médecin responsable associé à une ou plusieurs UF.
    
    Correspond au segment PV1-7 (Attending Doctor) en HL7
    et à Encounter.participant[role=ATND].individual (Practitioner) en FHIR.
    
    Identifié par RPPS (Répertoire Partagé des Professionnels de Santé)
    et/ou ADELI (Automatisation DEs LIstes).
    """
    __tablename__ = "medecinresponsable"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Identifiants nationaux
    rpps: Optional[str] = Field(default=None, index=True, description="Numéro RPPS (11 chiffres)")
    adeli: Optional[str] = Field(default=None, index=True, description="Numéro ADELI (9 chiffres)")
    
    # Identité (depuis XCN datatype)
    family_name: Optional[str] = Field(default=None, description="Nom de famille (XCN-2)")
    given_name: Optional[str] = Field(default=None, description="Prénom (XCN-3)")
    middle_name: Optional[str] = Field(default=None, description="Deuxième prénom (XCN-4)")
    prefix: Optional[str] = Field(default=None, description="Titre (Dr, Pr, XCN-6)")
    suffix: Optional[str] = Field(default=None, description="Suffixe (XCN-5)")
    
    # Informations complémentaires
    specialty: Optional[str] = Field(default=None, description="Spécialité médicale")
    email: Optional[str] = Field(default=None, description="Email professionnel")
    phone: Optional[str] = Field(default=None, description="Téléphone professionnel")
    
    # Métadonnées
    active: bool = Field(default=True, description="Praticien actif")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Relations
    uf_responsabilite: List["UniteFonctionnelle"] = Relationship(
        back_populates="medecin_responsable",
        sa_relationship_kwargs={"foreign_keys": "UniteFonctionnelle.medecin_responsable_id"}
    )
    dossiers: List["Dossier"] = Relationship(back_populates="medecin_responsable")
    mouvements: List["Mouvement"] = Relationship(back_populates="medecin_responsable")
    
    def __repr__(self):
        name = f"{self.prefix or ''} {self.given_name or ''} {self.family_name or ''}".strip()
        ids = []
        if self.rpps:
            ids.append(f"RPPS:{self.rpps}")
        if self.adeli:
            ids.append(f"ADELI:{self.adeli}")
        id_str = f" ({', '.join(ids)})" if ids else ""
        return f"<MedecinResponsable {name}{id_str}>"
    
    def get_full_name(self) -> str:
        """Retourne le nom complet du médecin"""
        parts = []
        if self.prefix:
            parts.append(self.prefix)
        if self.given_name:
            parts.append(self.given_name)
        if self.middle_name:
            parts.append(self.middle_name)
        if self.family_name:
            parts.append(self.family_name)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts) if parts else "Médecin inconnu"
    
    def get_identifier(self) -> Optional[str]:
        """Retourne l'identifiant principal (RPPS prioritaire)"""
        return self.rpps or self.adeli
