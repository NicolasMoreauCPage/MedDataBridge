from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel

from app.models_shared import SystemEndpoint

if TYPE_CHECKING:
    from app.models_structure import EntiteJuridique, GHTContext, IdentifierNamespace, EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit



    @property
    def code(self) -> Optional[str]:
        """Compatibility property: return oid if present, otherwise system."""
        return getattr(self, "oid", None) or getattr(self, "system", None)

    # Conformité stricte IHE PAM France (désactive A08). Active par défaut.
    strict_pam_fr: bool = Field(default=True, description="Si vrai, événements A08 interdits (émission/réception).")

    # Relations
    ght_context_id: int = Field(foreign_key="ghtcontext.id")
    ght_context: GHTContext = Relationship(back_populates="entites_juridiques")
    entites_geographiques: List["EntiteGeographique"] = Relationship(back_populates="entite_juridique")
    endpoints: List["SystemEndpoint"] = Relationship(back_populates="entite_juridique")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="entite_juridique")

    @property
    def namespace_oid(self) -> Optional[str]:
        """Return the OID of the primary IdentifierNamespace linked to this EJ, if any."""
        try:
            if self.namespaces and len(self.namespaces) > 0:
                return getattr(self.namespaces[0], "oid", None)
        except Exception:
            return None
        return None

    @property
    def finess(self) -> Optional[str]:
        """Compatibility property returning the FINESS identifier for the EJ.

        Some code/tests expect `ej.finess`; the canonical field here is
        `finess_ej`, so expose it via this property for backwards compatibility.
        """
        return getattr(self, "finess_ej", None)

    address_postalcode: Optional[str] = None
    address_city: Optional[str] = None
    address_country: Optional[str] = "FR"
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Catégorisation
    category_code: Optional[str] = None  # Code catégorie établissement
    category_name: Optional[str] = None
    category_sae: Optional[str] = None
    city_insee_code: Optional[str] = None
    type: Optional[str] = None  # Typologie (ex: MCO)

    # État
    is_active: bool = Field(default=True)

    # Dates (format HL7 YYYYMMDD pour compatibilité tests)
    opening_date: Optional[str] = None
    activation_date: Optional[str] = None
    closing_date: Optional[str] = None
    deactivation_date: Optional[str] = None

    # Responsable(s)
    responsible_id: Optional[str] = None
    responsible_name: Optional[str] = None
    responsible_firstname: Optional[str] = None
    responsible_rpps: Optional[str] = None
    responsible_adeli: Optional[str] = None
    responsible_specialty: Optional[str] = None

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relations
    # Make the foreign key optional for POC/tests: some imports create
    # geographical entities without a juridical entity present.
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    entite_juridique: Optional[EntiteJuridique] = Relationship(back_populates="entites_geographiques")
    poles: List["Pole"] = Relationship(back_populates="entite_geo")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="entite_geographique")

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models_structure import Pole, Service, UniteHebergement, Chambre, Lit
