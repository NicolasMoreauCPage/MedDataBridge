from typing import Optional, List, TYPE_CHECKING, ForwardRef
from datetime import date, datetime
from pydantic import model_validator
from sqlalchemy import Column
from sqlalchemy.types import TypeDecorator, Date as SA_Date
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship, Session

from app.models_identifiers import Identifier, IdentifierType
import app.models_contacts

if TYPE_CHECKING:
    from app.models_contacts import PatientContact, VenueContact


class IdentityReliabilityCode(str, Enum):
    """
    Codes de fiabilité d'identité selon RNIV (Référentiel National d'Identification)
    Compatible avec HL7 Table 0445 étendue pour la France
    """
    VALI = "VALI"  # Identité validée (présence INS-A dans annuaire national)
    QUAL = "QUAL"  # Identité qualifiée (5 traits stricts vérifiés)
    PROV = "PROV"  # Identité provisoire (en cours de qualification)
    VIDE = "VIDE"  # Identité fictive (patient non identifiable)
    DOUTE = "DOUTE"  # Identité douteuse (incohérences détectées)
    DOUB = "DOUB"  # Doublon détecté (fusion requise)
    FICTI = "FICTI"  # Fictive (alias HL7 de VIDE, compatibilité)


class INSType(str, Enum):
    """Type d'Identifiant National de Santé selon RNIV"""
    NIR = "NIR"  # Numéro d'Inscription au Répertoire (Sécurité Sociale)
    INS_C = "INS-C"  # INS Calculé (pour personnes sans NIR)


class DossierType(str, Enum):
    """Type de dossier patient"""
    HOSPITALISE = "hospitalise"        # Hospitalisation complète
    HOSPITALISATION_MIXTE = "hospitalisation_mixte"  # Hospitalisation mixte (jour + nuit)
    HOSPITALISATION_PARTIELLE = "hospitalisation_partielle"  # Hospitalisation partielle
    EXTERNE = "externe"               # Consultation externe
    URGENCE = "urgence"              # Passage aux urgences
    
# --- Générateur de séquences générique ---
class Sequence(SQLModel, table=True):
    name: str = Field(primary_key=True)   # ex: "dossier", "venue", "mouvement"
    value: int = 0
    # no __table_args__ here to avoid redefinition issues during tests

# --- Patient ---
class Patient(SQLModel, table=True):
    """
    Modèle Patient conforme aux normes françaises et RGPD.
    
    IMPORTANT RGPD France :
    - race et religion : INTERDITS en France (Article 9 RGPD + loi Informatique et Libertés)
    - Ces champs sont conservés en DB pour compatibilité legacy mais NE DOIVENT PAS être collectés
    - gender : sexe administratif unique (pas de duplication avec administrative_gender)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    # patient_seq supprimé, utiliser id comme identifiant métier unique
    external_id: Optional[str] = None  # Identifiant du système source externe
    identifier: Optional[str] = Field(default=None, index=True)  # Identifiant principal (peut être NIR ou autre)
    ght_context_id: Optional[int] = Field(default=None, foreign_key="ghtcontext.id")  # Association au contexte GHT
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")  # Association à l'EJ
    
    # Identité
    family: str = Field(alias="nom")  # Nom de famille (obligatoire)
    given: Optional[str] = None  # Prénom
    middle: Optional[str] = None  # Deuxième prénom
    prefix: Optional[str] = None  # Civilité (M./Mme/Mlle)
    suffix: Optional[str] = None  # Suffixe (Jr., III, etc.)
    birth_family: Optional[str] = None  # Nom de naissance (nom de jeune fille) - PID-5 type L
    class _FlexibleDate(TypeDecorator):
        impl = SA_Date

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if isinstance(value, date):
                return value
            # Accept strings in common HL7 formats and convert
            if isinstance(value, str):
                v = value.strip()
                for fmt in ("%Y%m%d", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(v, fmt).date()
                    except Exception:
                        continue
            return value

    birth_date: Optional[date] = Field(default=None, sa_column=Column(_FlexibleDate(), nullable=True))  # Date de naissance
    gender: Optional[str] = None  # Sexe administratif (male/female/other/unknown)
    
    # Adresse d'habitation (PID-11)
    address: Optional[str] = None  # PID-11.1 - Adresse (numéro et rue)
    city: Optional[str] = None  # PID-11.3 - Ville
    state: Optional[str] = None  # PID-11.4 - Département/Région
    postal_code: Optional[str] = None  # PID-11.5 - Code postal
    country: Optional[str] = None  # PID-11.6 - Pays (code ISO: FR, BE, CH, etc.)
    
    # Téléphones (PID-13) - Multi-valué
    phone: Optional[str] = None  # PID-13.1 - Téléphone principal/fixe
    mobile: Optional[str] = None  # PID-13.2 - Téléphone mobile/cellulaire
    work_phone: Optional[str] = None  # PID-13.3 - Téléphone professionnel
    email: Optional[str] = None  # Email
    
    # Lieu de naissance (adresse complète) - Complément PID-23
    birth_address: Optional[str] = None  # Rue de naissance (optionnel)
    birth_city: Optional[str] = None  # Ville de naissance (PID-23 dans HL7 v2.5 - texte libre)
    birth_state: Optional[str] = None  # Département/Région de naissance
    birth_postal_code: Optional[str] = None  # Code postal de naissance
    birth_country: Optional[str] = None  # Pays de naissance (code ISO: FR, etc.)
    
    # Statut de l'identité (PID-32) - OBLIGATOIRE IHE PAM France pour INS
    identity_reliability_code: Optional[str] = None  # HL7 Table 0445/RNIV: VIDE/PROV/VALI/DOUTE/FICTI/QUAL/DOUB
    identity_reliability_date: Optional[date] = Field(default=None, sa_column=Column(_FlexibleDate(), nullable=True))  # Date de validation de l'identité
    identity_reliability_source: Optional[str] = None  # Source de validation (CNI, Passeport, Acte naissance, etc.)
    identity_matrix_code: Optional[str] = None  # Code Matrice de Gestion d'Identité (MGI) utilisée - RNIV
    
    # INS - Identifiant National de Santé (RNIV)
    nir: Optional[str] = None  # Numéro d'Inscription au Répertoire (NIR) - Numéro de sécurité sociale français (PID-3 NH)
    ins_c: Optional[str] = None  # INS Calculé - Pour personnes sans NIR (RNIV)
    ins_type: Optional[str] = None  # Type d'INS: "NIR" ou "INS-C" (RNIV)
    ins_in_annuaire: Optional[bool] = None  # INS-A: INS présent dans annuaire national INSI (TéléSanté) - RNIV
    ins_last_query_date: Optional[date] = Field(default=None, sa_column=Column(_FlexibleDate(), nullable=True))  # Date dernier appel service INSI - RNIV
    
    # Prénoms structurés (RNIV - Traits Stricts)
    birth_given_names: Optional[str] = None  # Liste complète prénoms état civil (ordre officiel, séparés par espace) - RNIV
    used_given_name: Optional[str] = None  # Prénom d'usage/usuel (peut différer du 1er prénom) - RNIV
    birth_insee_code: Optional[str] = None  # Code INSEE lieu naissance (5 chars: 75056=Paris, 2A004=Ajaccio) - RNIV Trait Strict
    
    # Informations administratives
    marital_status: Optional[str] = None  # Statut marital (codes HL7: S/M/D/W/P/A/U)
    mothers_maiden_name: Optional[str] = None  # Nom de jeune fille de la mère (vérification identité)
    nationality: Optional[str] = None  # Nationalité (code pays ISO, ex: FR)
    place_of_birth: Optional[str] = None  # Lieu de naissance
    primary_care_provider: Optional[str] = None  # Médecin traitant déclaré

    dossiers: List["Dossier"] = Relationship(back_populates="patient")
    identifiers: List["Identifier"] = Relationship(back_populates="patient")
    contacts: List["PatientContact"] = Relationship(back_populates="patient")

    # Backwards-compat properties used by tests/templates expecting French names
    @property
    def nom(self) -> str:
        return self.family

    @nom.setter
    def nom(self, value: str) -> None:
        self.family = value

    @property
    def prenom(self) -> Optional[str]:
        return self.given

    @prenom.setter
    def prenom(self, value: str) -> None:
        self.given = value

    @model_validator(mode="before")
    def _coerce_dates(cls, values: dict) -> dict:
        """Coerce date strings (YYYYMMDD or YYYY-MM-DD) to Python date objects.

        This accepts common HL7 date formats used in tests and in HL7 parsers.
        """
        def _parse_date(v):
            if v is None:
                return None
            if isinstance(v, date):
                return v
            if isinstance(v, str):
                v = v.strip()
                for fmt in ("%Y%m%d", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(v, fmt).date()
                    except Exception:
                        continue
            return v

        # Fields to coerce
        for key in ("birth_date", "identity_reliability_date", "ins_last_query_date"):
            if key in values:
                values[key] = _parse_date(values.get(key))

        return values


# --- Dossier ---
class Dossier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_seq: int = Field(index=True, unique=True)       # identifiant métier unique
    patient_id: int = Field(foreign_key="patient.id")
    admit_time: datetime
    discharge_time: Optional[datetime] = None
    dossier_type: DossierType = Field(default=DossierType.HOSPITALISE, description="Type de dossier (hospitalisé, externe, urgence)")
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    # UF responsable du dossier (= UF médicale = UF de responsabilité médicale)
    uf_responsabilite: Optional[str] = None                 # Code UF responsable/médicale (ex: "CARDIO")

    # Extensions / IHE PAM additions (optional)
    admission_type: Optional[str] = None
    admission_source: Optional[str] = None  # Source d'admission
    attending_provider: Optional[str] = None
    # Champs métier
    reason: Optional[str] = None  # Motif d'admission (utiliser vocabulaire FR)
    current_state: Optional[str] = None  # État actuel du dossier (utiliser vocabulaire FR)
    patient: Patient = Relationship(back_populates="dossiers")
    venues: List["Venue"] = Relationship(back_populates="dossier")
    identifiers: List["Identifier"] = Relationship(back_populates="dossier")

# --- Venue (appartient à un Dossier) ---
class Venue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    venue_seq: int = Field(index=True, unique=True)         # identifiant métier unique
    code: Optional[str] = None                               # code de localisation (PV1-3)
    label: Optional[str] = None                              # libellé descriptif de la venue
    assigned_location: Optional[str] = None                  # localisation assignée (lit/chambre)
    dossier_id: int = Field(foreign_key="dossier.id")
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    uf_responsabilite: Optional[str] = None
    # ZBE segment fields (IHE PAM France)
    # uf_responsabilite (above) = UF médicale (ZBE-7), uf_soins (below) = UF de soins (ZBE-8)
    uf_soins_code: Optional[str] = None
    uf_soins_label: Optional[str] = None
    nature: Optional[str] = None  # Movement nature code (S,H,M,L,D,SM)
    start_time: datetime
    dossier: Dossier = Relationship(back_populates="venues")
    mouvements: List["Mouvement"] = Relationship(back_populates="venue")
    identifiers: List["Identifier"] = Relationship(back_populates="venue")
    contacts: List["VenueContact"] = Relationship(back_populates="venue")

 # --- Mouvement (appartient à une Venue) ---
# ...existing code...

class Mouvement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mouvement_seq: int = Field(index=True, unique=True)     # identifiant métier unique
    venue_id: int = Field(foreign_key="venue.id")
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    # Type de message HL7 (ex: "ADT^A01"). Conservé pour compat UI/ancienne donnée.
    # La logique métier doit utiliser trigger_event (A01, A03, A21, ...).
    type: Optional[str] = None
    when: datetime  # Date/heure du mouvement (début)
    end_time: Optional[datetime] = None  # Fin (pour mapping FHIR Encounter period.end)
    location: Optional[str] = None
    # Extensions
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    reason: Optional[str] = None
    performer: Optional[str] = None
    status: Optional[str] = None
    note: Optional[str] = None
    movement_type: Optional[str] = None  # Type de mouvement (français)
    movement_reason: Optional[str] = None  # Raison du mouvement
    performer_role: Optional[str] = None  # Rôle de l'intervenant
    trigger_event: Optional[str] = None  # Code IHE PAM de l'événement (A01, A03, A21, etc.) pour validation des transitions
    # Référence au mouvement annulé (pour A12/A13) via numéro de séquence, si connu
    cancelled_movement_seq: Optional[int] = None
    # ZBE compliance additions (migration 014)
    action: Optional[str] = Field(default=None, description="ZBE-4 Action: INSERT|UPDATE|CANCEL")
    is_historic: bool = Field(default=False, description="ZBE-5 Historic flag (true if Y)")
    original_trigger: Optional[str] = Field(default=None, description="ZBE-6 Original trigger event for UPDATE/CANCEL")
    nature: Optional[str] = Field(default=None, description="ZBE-9 Movement nature code (S,H,M,L,D,SM)")
    uf_responsabilite: Optional[str] = Field(default=None, description="ZBE-7 UF médicale (= UF de responsabilité)")
    uf_soins_code: Optional[str] = Field(default=None, description="ZBE-8 XON component 10 UF soins code")
    uf_soins_label: Optional[str] = Field(default=None, description="ZBE-8 XON component 1 UF soins label")
    venue: Venue = Relationship(back_populates="mouvements")
    identifiers: List["Identifier"] = Relationship(back_populates="mouvement")

    class Config:
        # Allow extra fields passed by legacy tests/scripts (e.g. date_heure_mouvement,
        # type_mouvement) so they are retained on the model instance and can be
        # normalized in DB hooks before persistence.
        extra = "allow"

    # --- Compatibilité ascendante (anciens champs attendus par tests/anciens templates) ---
    @property
    def statut(self) -> Optional[str]:  # ancien nom
        return self.status

    @statut.setter
    def statut(self, value: Optional[str]):
        self.status = value

    @property
    def date_debut(self) -> datetime:
        return self.when

    @property
    def date_fin(self) -> Optional[datetime]:
        return self.end_time

    @property
    def dossier_id(self) -> Optional[int]:
        try:
            return self.venue.dossier_id if self.venue else None
        except Exception:
            return None
