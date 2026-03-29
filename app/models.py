from typing import Optional, List, TYPE_CHECKING, ForwardRef
from datetime import date, datetime
from pydantic import model_validator
from sqlalchemy import Column
from sqlalchemy.types import TypeDecorator, Date as SA_Date
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship, Session

from app.models_identifiers import Identifier, IdentifierType
import app.models_contacts
import app.models_structure

if TYPE_CHECKING:
    from app.models_contacts import PatientContact, VenueContact
    from app.models_practitioners import MedecinResponsable


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
    
    # Médecin responsable du dossier (PV1-7 Attending Doctor)
    medecin_responsable_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")

    # Extensions / IHE PAM additions (optional)
    admission_type: Optional[str] = None
    admission_source: Optional[str] = None  # Source d'admission
    attending_provider: Optional[str] = None
    # Champs métier
    reason: Optional[str] = None  # Motif d'admission (utiliser vocabulaire FR)
    current_state: Optional[str] = None  # État actuel du dossier (utiliser vocabulaire FR)
    
    # Cotations HPRIM
    has_cotations: bool = Field(default=False, description="Indique si le dossier a des cotations")
    cotations_count: int = Field(default=0, description="Nombre de cotations liées au dossier")
    
    # Relationships
    medecin_responsable: Optional["MedecinResponsable"] = Relationship(back_populates="dossiers")
    
    patient: Patient = Relationship(back_populates="dossiers")
    venues: List["Venue"] = Relationship(back_populates="dossier")
    identifiers: List["Identifier"] = Relationship(back_populates="dossier")
    ngap_acts: List["NGAPAct"] = Relationship(back_populates="dossier")
    ucd_acts: List["UCDAct"] = Relationship(back_populates="dossier")
    lpp_acts: List["LPPAct"] = Relationship(back_populates="dossier")
    ccam_acts: List["CCAMAct"] = Relationship(back_populates="dossier")
    contracts: List["Contract"] = Relationship(back_populates="dossier")

# --- Venue (appartient à un Dossier) ---
class Venue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    venue_seq: int = Field(index=True, unique=True)         # identifiant métier unique
    code: Optional[str] = None                               # code de localisation (PV1-3)
    label: Optional[str] = None                              # libellé descriptif de la venue
    assigned_location: Optional[str] = None                  # localisation assignée (lit/chambre)
    dossier_id: int = Field(foreign_key="dossier.id")
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    chambre_id: Optional[int] = Field(default=None, foreign_key="chambre.id")  # Chambre assignée
    lit_id: Optional[int] = Field(default=None, foreign_key="lit.id")          # Lit assigné
    uf_responsabilite: Optional[str] = None
    # ZBE segment fields (IHE PAM France)
    # uf_responsabilite (above) = UF médicale (ZBE-7), uf_soins (below) = UF de soins (ZBE-8)
    uf_soins_code: Optional[str] = None
    uf_soins_label: Optional[str] = None
    nature: Optional[str] = None  # Movement nature code (S,H,M,L,D,SM)
    hospital_service: Optional[str] = None  # Service hospitalier
    attending_provider: Optional[str] = None  # Médecin responsable
    start_time: datetime
    dossier: Dossier = Relationship(back_populates="venues")
    mouvements: List["Mouvement"] = Relationship(back_populates="venue")
    identifiers: List["Identifier"] = Relationship(back_populates="venue")
    contacts: List["VenueContact"] = Relationship(back_populates="venue")
    chambre: Optional["Chambre"] = Relationship(back_populates="venues")
    lit: Optional["Lit"] = Relationship(back_populates="venues")

 # --- Mouvement (appartient à une Venue) ---
# ...existing code...

class Mouvement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mouvement_seq: int = Field(index=True, unique=True)     # identifiant métier unique
    venue_id: int = Field(foreign_key="venue.id")
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    
    # Médecin responsable du mouvement (PV1-7 Attending Doctor)
    medecin_responsable_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    medecin_responsable: Optional["MedecinResponsable"] = Relationship(back_populates="mouvements")
    
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


# --- Actes Médicaux (NGAP, UCD, LPP) ---

class NGAPAct(SQLModel, table=True):
    """
    Acte NGAP - Nomenclature Générale des Actes Professionnels
    Conforme à HPRIM XML v2.4 msgEvenementsServeurActes typeActeNgap
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    mouvement_id: Optional[int] = Field(default=None, foreign_key="mouvement.id", description="Optionnel: lien vers mouvement spécifique")

    # Identifiant unique de l'acte
    identifiant_acte: Optional[str] = Field(default=None, description="Identifiant unique de l'acte")

    # Codes NGAP (obligatoires)
    lettre_cle: str = Field(description="Lettre-clé NGAP (ex: A, AMI, APC, C, V, K)")
    coefficient: float = Field(description="Coefficient multiplicateur NGAP")
    denombrement: Optional[int] = Field(default=1, description="Dénombrement (nombre d'actes, défaut: 1)")

    # Quantité ou position dentaire (choix exclusif)
    quantite: Optional[int] = Field(default=None, description="Quantité")
    position_dentaire: Optional[str] = Field(default=None, description="Position dentaire")

    # Date/heure d'exécution (obligatoire)
    execute_date: datetime = Field(description="Date et heure d'exécution de l'acte")

    # Numéro de séance (pour actes en série)
    numero_seance: Optional[int] = Field(default=None, description="Numéro de séance")

    # Codes NABM (Nomenclature des Actes de Biologie Médicale)
    nabm_codes: Optional[str] = Field(default=None, description="Codes NABM séparés par des virgules")

    # Minoration/Majoration
    majoration_pourcentage: Optional[int] = Field(default=None, description="Pourcentage de majoration")
    majoration_coefficient: Optional[float] = Field(default=None, description="Coefficient de majoration")
    minoration_pourcentage: Optional[int] = Field(default=None, description="Pourcentage de minoration")
    minoration_coefficient: Optional[float] = Field(default=None, description="Coefficient de minoration")

    # Prise en charge
    risque: Optional[str] = Field(default=None, description="Code risque (2 chiffres)")
    entente_prealable: Optional[str] = Field(default=None, description="Entente préalable (d/da/na)")
    indicateur_parcours_soins: Optional[str] = Field(default=None, description="Indicateur parcours de soins (h/m)")
    date_demande_accord: Optional[date] = Field(default=None, description="Date demande d'accord préalable")

    # Montant et facturation
    montant_total: Optional[float] = Field(default=None, description="Montant total en euros")
    montant_depassement: Optional[float] = Field(default=None, description="Montant de dépassement")
    motif_depassement: Optional[str] = Field(default=None, description="Motif dépassement (d/e/f/n/da)")
    numero_facture: Optional[str] = Field(default=None, description="Numéro de facture")

    # BHN/PHN (Base/Plafond Honoraires Nocturnes)
    bhn_phn_montant: Optional[float] = Field(default=None, description="Montant BHN/PHN")

    # Commentaire libre
    commentaire: Optional[str] = Field(default=None, description="Commentaire libre")

    # Attributs HPRIM
    action: str = Field(default="creation", description="Action (creation/modification/suppression)")
    facturable: bool = Field(default=True, description="Acte facturable")
    execution_nuit: bool = Field(default=False, description="Exécution de nuit")
    execution_dimanche_ferie: bool = Field(default=False, description="Exécution dimanche ou jour férié")
    acte_hors_nomenclature: bool = Field(default=False, description="Acte hors nomenclature")
    rapport_exoneration: Optional[str] = Field(default=None, description="Rapport exonération (C/7/R/4)")
    gratuit: bool = Field(default=False, description="Acte gratuit")
    valide: bool = Field(default=False, description="Acte validé")
    facture: str = Field(default="non", description="Acte facturé (oui/non/trd/ec)")
    portee_cle: str = Field(default="n", description="Portée de la clé (n/r/d)")
    activite_recherche: bool = Field(default=False, description="Activité de recherche")
    code_prestation: Optional[str] = Field(default=None, description="Code prestation")

    # Relations avec professionnels de santé
    dossier: Dossier = Relationship(back_populates="ngap_acts")
    prestataire_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    prestataire: Optional["MedecinResponsable"] = Relationship(back_populates="ngap_acts")

    # Métadonnées de traçabilité
    date_action: Optional[datetime] = Field(default=None, description="Date de l'action (création/modification)")
    acteur_id: Optional[int] = Field(default=None, description="ID du professionnel ayant effectué l'action")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UCDAct(SQLModel, table=True):
    """
    Acte UCD - Unité Commune de Dispensation (Médicaments)
    Conforme à HPRIM XML v2.4 msgEvenementsServeurActes typeUCD
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    mouvement_id: Optional[int] = Field(default=None, foreign_key="mouvement.id", description="Optionnel: lien vers mouvement spécifique")

    # Identifiant unique de l'acte
    identifiant_acte: Optional[str] = Field(default=None, description="Identifiant unique de l'acte")

    # Codes UCD (Code CIP-13 obligatoire)
    code_interne_ucd: Optional[str] = Field(default=None, description="Code interne UCD (35 car)")
    code_ucd: str = Field(description="Code UCD / Code CIP-13 (13 chiffres)")
    code_commercial: Optional[str] = Field(default=None, description="Code commercial (120 car)")

    # Dénomination du médicament (optionnelle côté modèle, mais toujours renseignée par le seed)
    denomination_libelle: Optional[str] = Field(default=None, description="Libellé/dénomination du médicament")
    denomination_dosage: Optional[str] = Field(default=None, description="Dosage (ex: 1000mg)")
    denomination_forme: Optional[str] = Field(default=None, description="Forme galénique (ex: comprimé)")

    # Date (obligatoire) avec nature optionnelle
    execute_date: datetime = Field(description="Date de dispensation/administration")
    nature_date: Optional[str] = Field(default=None, description="Nature de la date (prescription/dispensation/administration)")

    # Quantité fractionnée (obligatoire)
    quantite: float = Field(description="Quantité fractionnée (décimal positif)")

    # Montants et tarification
    taux_tva: Optional[float] = Field(default=None, description="Taux de TVA en pourcentage")
    montant_unitaire_achat_ttc: Optional[float] = Field(default=None, description="Montant unitaire achat TTC")
    montant_unitaire_achat_ht: Optional[float] = Field(default=None, description="Montant unitaire achat HT")
    montant_ecart_indemnisable: Optional[float] = Field(default=None, description="Montant écart indemnisable")
    montant_unitaire_facture_ttc: Optional[float] = Field(default=None, description="Montant unitaire facturé TTC")
    montant_unitaire_facture_ht: Optional[float] = Field(default=None, description="Montant unitaire facturé HT")
    montant_marge_retrocession: Optional[float] = Field(default=None, description="Montant marge rétrocession")
    montant_reconstitution: Optional[float] = Field(default=None, description="Montant reconstitution")

    # Prise en charge
    risque: Optional[str] = Field(default=None, description="Code risque (2 chiffres)")
    entente_prealable: Optional[str] = Field(default=None, description="Entente préalable (d/da/na)")
    indicateur_parcours_soins: Optional[str] = Field(default=None, description="Indicateur parcours de soins (h/m)")
    date_demande_accord: Optional[date] = Field(default=None, description="Date demande d'accord préalable")

    # Nature de prestation UCD
    nature_prestation: Optional[str] = Field(default=None, description="Nature prestation UCD")

    # Fournisseur
    siret_fournisseur: Optional[str] = Field(default=None, description="SIRET fournisseur (14 chiffres)")
    numero_lot: Optional[str] = Field(default=None, description="Numéro de lot (15 car)")

    # Code indication Liste En Sus
    code_indication_les: Optional[str] = Field(default=None, description="Code indication LES (format I999999 ou 7-8 car)")

    # Commentaire libre
    commentaire: Optional[str] = Field(default=None, description="Commentaire libre")

    # Attributs HPRIM
    action: str = Field(default="creation", description="Action (creation/modification/suppression)")
    facturable: bool = Field(default=True, description="Acte facturable")
    gratuit: bool = Field(default=False, description="Acte gratuit")
    valide: bool = Field(default=False, description="Acte validé")
    facture: str = Field(default="non", description="Acte facturé (oui/non/trd/ec)")
    liberal: bool = Field(default=False, description="En exercice libéral")
    retrocession: bool = Field(default=False, description="Rétrocession")
    essai_therapeutique: bool = Field(default=False, description="Essai thérapeutique")

    # Relations avec professionnels de santé
    dossier: Dossier = Relationship(back_populates="ucd_acts")
    prescripteur_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    prescripteur: Optional["MedecinResponsable"] = Relationship(
        back_populates="ucd_acts_prescripteur",
        sa_relationship_kwargs={"foreign_keys": "UCDAct.prescripteur_id"}
    )
    prestataire_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    prestataire: Optional["MedecinResponsable"] = Relationship(
        back_populates="ucd_acts_prestataire",
        sa_relationship_kwargs={"foreign_keys": "UCDAct.prestataire_id"}
    )

    # Métadonnées de traçabilité
    date_action: Optional[datetime] = Field(default=None, description="Date de l'action (création/modification)")
    acteur_id: Optional[int] = Field(default=None, description="ID du professionnel ayant effectué l'action")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class LPPAct(SQLModel, table=True):
    """
    Acte LPP - Liste des Produits et Prestations (Dispositifs Médicaux)
    Conforme à HPRIM XML v2.4 msgEvenementsServeurActes typeLPP
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    mouvement_id: Optional[int] = Field(default=None, foreign_key="mouvement.id", description="Optionnel: lien vers mouvement spécifique")

    # Identifiant unique de l'acte
    identifiant_acte: Optional[str] = Field(default=None, description="Identifiant unique de l'acte")

    # Date de pose/utilisation (obligatoire)
    execute_date: datetime = Field(description="Date et heure de pose/utilisation du dispositif")

    # Codes LPP
    code_interne_lpp: Optional[str] = Field(default=None, description="Code interne LPP (35 car)")
    code_lpp: Optional[str] = Field(default=None, description="Code LPP (13 chiffres)")
    code_commercial_lpp: Optional[str] = Field(default=None, description="Code commercial LPP (120 car)")

    # Dénomination (optionnelle côté modèle, mais toujours renseignée par le seed)
    denomination_libelle: Optional[str] = Field(default=None, description="Libellé du dispositif médical")

    # Fournisseur (obligatoire, choix entre SIRET ou identifiant)
    siret_fournisseur: Optional[str] = Field(default=None, description="SIRET fournisseur (14 chiffres)")
    identifiant_fournisseur_code: Optional[str] = Field(default=None, description="Code identifiant fournisseur (17 car)")
    identifiant_fournisseur_libelle: Optional[str] = Field(default=None, description="Libellé identifiant fournisseur (120 car)")

    # Montants et tarification (obligatoire: montant unitaire facturé TTC)
    taux_tva: Optional[float] = Field(default=None, description="Taux de TVA en pourcentage")
    montant_unitaire_achat_ttc: Optional[float] = Field(default=None, description="Montant unitaire achat TTC")
    montant_ecart_indemnisable: Optional[float] = Field(default=None, description="Montant écart indemnisable")
    montant_unitaire_facture_ttc: float = Field(description="Montant unitaire facturé TTC (obligatoire)")

    # Quantité (obligatoire)
    quantite: int = Field(description="Quantité (nombre entier positif)")

    # Prise en charge
    risque: Optional[str] = Field(default=None, description="Code risque (2 chiffres)")
    entente_prealable: Optional[str] = Field(default=None, description="Entente préalable (d/da/na)")
    indicateur_parcours_soins: Optional[str] = Field(default=None, description="Indicateur parcours de soins (h/m)")
    date_demande_accord: Optional[date] = Field(default=None, description="Date demande d'accord préalable")

    # Traçabilité produit
    date_peremption: Optional[date] = Field(default=None, description="Date de péremption")
    numero_serie: Optional[str] = Field(default=None, description="Numéro de série")
    numero_lot: Optional[str] = Field(default=None, description="Numéro de lot (15 car)")
    iud_id: Optional[str] = Field(default=None, description="IUD/UDI (Identifiant Unique du Dispositif, 14-24 car)")

    # Nature de prestation LPP
    nature_prestation: Optional[str] = Field(default=None, description="Nature prestation LPP")

    # Commentaire libre
    commentaire: Optional[str] = Field(default=None, description="Commentaire libre")

    # Attributs HPRIM
    action: str = Field(default="creation", description="Action (creation/modification/suppression)")
    facturable: bool = Field(default=True, description="Acte facturable")
    gratuit: bool = Field(default=False, description="Acte gratuit")
    valide: bool = Field(default=False, description="Acte validé")
    facture: str = Field(default="non", description="Acte facturé (oui/non/trd/ec)")
    liberal: bool = Field(default=False, description="En exercice libéral")
    signe: bool = Field(default=False, description="Acte signé électroniquement")

    # Relations avec professionnels de santé
    dossier: Dossier = Relationship(back_populates="lpp_acts")
    prestataire_id: Optional[int] = Field(default=None, foreign_key="medecinresponsable.id")
    prestataire: Optional["MedecinResponsable"] = Relationship(back_populates="lpp_acts")

    # Métadonnées de traçabilité
    date_action: Optional[datetime] = Field(default=None, description="Date de l'action (création/modification)")
    acteur_id: Optional[int] = Field(default=None, description="ID du professionnel ayant effectué l'action")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class CCAMAct(SQLModel, table=True):
    """
    Acte CCAM - Classification Commune des Actes Médicaux
    Conforme à HPRIM XML v2.4 msgEvenementsServeurActes typeActeCcam
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id")
    mouvement_id: Optional[int] = Field(default=None, foreign_key="mouvement.id", description="Optionnel: lien vers mouvement spécifique")

    # Identifiant unique de l'acte (typeIdentifiant HPRIM)
    identifiant_acte: Optional[str] = Field(default=None, description="Identifiant unique de l'acte")

    # Codes CCAM (obligatoires)
    code_acte: str = Field(description="Code acte CCAM (format: 4 lettres + 3 chiffres, ex: HBMD001)")
    code_acte_extension_pmsi: Optional[str] = Field(default=None, description="Code extension PMSI CCAM")
    code_activite: str = Field(description="Code activité CCAM (2 chiffres: 01-08)")
    code_phase: str = Field(default="0", description="Code phase CCAM (2 chiffres: 0, 1, 2)")

    # Date/heure d'exécution (obligatoire)
    execute_date: datetime = Field(description="Date et heure d'exécution de l'acte")

    # Modificateurs CCAM (ex: Z1, K50, etc.)
    modificateurs: Optional[str] = Field(default=None, description="Modificateurs CCAM séparés par des virgules")
    code_association_non_prevue: Optional[str] = Field(default=None, description="Code association non prévue (1 car)")
    code_extension_documentaire: Optional[str] = Field(default=None, description="Code extension documentaire (1 car)")

    # Quantité / Positions dentaires (choix exclusif)
    quantite: Optional[int] = Field(default=1, description="Quantité (défaut: 1)")
    positions_dentaires: Optional[str] = Field(default=None, description="Positions dentaires (max 32, séparées par des virgules)")

    # Montant et prise en charge
    montant_total: Optional[float] = Field(default=None, description="Montant total en euros")
    montant_depassement: Optional[float] = Field(default=None, description="Montant de dépassement")
    motif_depassement: Optional[str] = Field(default=None, description="Motif dépassement (d/e/f/n/da)")
    numero_forfait_technique: Optional[str] = Field(default=None, description="Numéro forfait technique (5 chiffres)")
    numero_facture: Optional[str] = Field(default=None, description="Numéro de facture (9 chiffres)")

    # Prise en charge
    risque: Optional[str] = Field(default=None, description="Code risque (2 chiffres)")
    entente_prealable: Optional[str] = Field(default=None, description="Entente préalable (d/da/na)")
    indicateur_parcours_soins: Optional[str] = Field(default=None, description="Indicateur parcours de soins (h/m)")
    date_demande_accord: Optional[date] = Field(default=None, description="Date demande d'accord préalable")

    # Acte principal (pour actes associés)
    identifiant_acte_principal: Optional[str] = Field(default=None, description="Identifiant de l'acte principal")
    code_acte_principal: Optional[str] = Field(default=None, description="Code CCAM de l'acte principal")

    # Radiothérapie (champs spécifiques si applicable)
    radiotherapie_seances: Optional[int] = Field(default=None, description="Nombre de séances de radiothérapie")
    radiotherapie_modalite: Optional[str] = Field(default=None, description="Modalité de radiothérapie")

    # Commentaire libre
    commentaire: Optional[str] = Field(default=None, description="Commentaire libre")

    # Attributs HPRIM
    action: str = Field(default="creation", description="Action (creation/modification/suppression)")
    rapport_exoneration: Optional[str] = Field(default=None, description="Rapport exonération (C/7/R/4)")
    facturable: bool = Field(default=True, description="Acte facturable (oui/non)")
    remboursement_exceptionnel: bool = Field(default=False, description="Remboursement exceptionnel")
    supplement_charges: Optional[str] = Field(default=None, description="Supplément charges (c)")
    valide: bool = Field(default=False, description="Acte validé (oui/non/validé)")
    facture: str = Field(default="non", description="Acte facturé (oui/non/trd/ec)")
    pmsi: Optional[str] = Field(default=None, description="Indicateur PMSI (g/ng/tr)")
    documentaire: bool = Field(default=False, description="Acte documentaire")
    gratuit: bool = Field(default=False, description="Acte gratuit")
    option_coordination: bool = Field(default=False, description="Option de coordination")
    prevention_amo_amc: bool = Field(default=False, description="TOP prévention action AMO/AMC")
    forfait_securite_environnement: Optional[str] = Field(default=None, description="Forfait sécurité environnement hospitalier")
    signe: bool = Field(default=False, description="Acte signé électroniquement")
    exoneration_ccam: Optional[str] = Field(default=None, description="Exonération CCAM (1-5, 7)")

    # Mode et discipline de traitement
    mode_traitement: Optional[str] = Field(default=None, description="Mode de traitement (19)")
    discipline_traitement: Optional[str] = Field(default=None, description="Discipline de traitement (0/7/35/750/753)")
    liberal: bool = Field(default=False, description="Acte en exercice libéral")

    # Relations avec professionnels de santé
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

    # Métadonnées de traçabilité
    date_action: Optional[datetime] = Field(default=None, description="Date de l'action (création/modification)")
    acteur_id: Optional[int] = Field(default=None, description="ID du professionnel ayant effectué l'action")
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


# Export models from models_structure for convenience
from app.models_structure import Chambre, Lit