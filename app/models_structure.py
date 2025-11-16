from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Pole(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    entite_geo_id: Optional[int] = Field(default=None, foreign_key="entitegeographique.id")
    entite_geo: Optional["EntiteGeographique"] = Relationship(back_populates="poles")
    services: List["Service"] = Relationship(back_populates="pole")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="pole")

class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    pole_id: Optional[int] = Field(default=None, foreign_key="pole.id")
    pole: Optional["Pole"] = Relationship(back_populates="services")
    unites_fonctionnelles: List["UniteFonctionnelle"] = Relationship(back_populates="service")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="service")

class UniteFonctionnelleActivityLink(SQLModel, table=True):
    """Table de liaison UF <-> UFActivity (many-to-many)."""
    uf_id: int = Field(foreign_key="unitefonctionnelle.id", primary_key=True)
    activity_id: int = Field(foreign_key="ufactivity.id", primary_key=True)


class UFActivity(SQLModel, table=True):
    """Code d'activité d'une UF (multi-valué)

    Permet d'indiquer qu'une UF pratique plusieurs activités (ex: urgences,
    hospitalisation, consultations). Conçu pour un mapping direct vers
    FHIR Location.type (via extensions fr-uf-type) et MFN Structure.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    display: Optional[str] = None
    system: Optional[str] = None  # Optionnel: URL du code system
    # Relations
    unites_fonctionnelles: List["UniteFonctionnelle"] = Relationship(
        back_populates="activities",
        link_model=UniteFonctionnelleActivityLink,
    )

class UniteFonctionnelle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    um_code: Optional[str] = None
    service_id: Optional[int] = Field(default=None, foreign_key="service.id")
    service: Optional["Service"] = Relationship(back_populates="unites_fonctionnelles")
    unites_hebergement: List["UniteHebergement"] = Relationship(back_populates="unite_fonctionnelle")
    activities: List[UFActivity] = Relationship(
        back_populates="unites_fonctionnelles",
        link_model=UniteFonctionnelleActivityLink,
    )
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="unite_fonctionnelle")

class UniteHebergement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    unite_fonctionnelle_id: Optional[int] = Field(default=None, foreign_key="unitefonctionnelle.id")
    unite_fonctionnelle: Optional["UniteFonctionnelle"] = Relationship(back_populates="unites_hebergement")
    chambres: List["Chambre"] = Relationship(back_populates="unite_hebergement")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="unite_hebergement")

class Chambre(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    unite_hebergement_id: Optional[int] = Field(default=None, foreign_key="unitehebergement.id")
    unite_hebergement: Optional["UniteHebergement"] = Relationship(back_populates="chambres")
    lits: List["Lit"] = Relationship(back_populates="chambre")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="chambre")

class Lit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    chambre_id: Optional[int] = Field(default=None, foreign_key="chambre.id")
    chambre: Optional["Chambre"] = Relationship(back_populates="lits")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="lit")

from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from app.models_shared import SystemEndpoint

class EntiteJuridique(SQLModel, table=True):
    """Structure juridique (ES_JURIDIQUE) - niveau 1"""
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, index=True, unique=True)  # CD
    global_identifier: Optional[str] = Field(default=None, index=True)  # ID_GLBL
    name: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    finess_ej: str = Field(index=True)  # FINESS entité juridique
    siren: Optional[str] = None
    siret: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: str = "FR"
    is_active: bool = Field(default=True)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    endpoints: List["SystemEndpoint"] = Relationship(back_populates="entite_juridique")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="entite_juridique")
    ght_context_id: Optional[int] = Field(default=None, foreign_key="ghtcontext.id")
    ght_context: Optional["GHTContext"] = Relationship(back_populates="entites_juridiques")

class GHTContext(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    code: str = Field(index=True, default="")
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    oid_racine: Optional[str] = None
    fhir_server_url: Optional[str] = None
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="ght_context")

    entites_juridiques: List["EntiteJuridique"] = Relationship(back_populates="ght_context")
    endpoints: List["SystemEndpoint"] = Relationship(back_populates="ght_context")

# --- ENUMS ---

class LocationStatus(str, Enum):
    """https://hl7.org/fhir/R4/valueset-location-status.html"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"

class LocationMode(str, Enum):
    """https://hl7.org/fhir/R4/valueset-location-mode.html"""
    INSTANCE = "instance"
    KIND = "kind"
    HOSPITALIZATION = "hospitalization"
    AMBULATORY = "ambulatory"
    VIRTUAL = "virtual"

class LocationPhysicalType(str, Enum):
    """http://terminology.hl7.org/ValueSet/location-physical-type + extensions FHIR France"""
    SI = "si"     # Site
    BU = "bu"     # Bâtiment
    WI = "wi"     # Aile (Wing)
    WA = "wa"     # Unité de soins (Ward)
    LV = "lv"     # Niveau/Étage (Level)
    FL = "fl"     # Étage
    RO = "ro"     # Chambre
    BD = "bd"     # Lit

# --- MODELS ---

class EntiteGeographique(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: str = Field(default_factory=lambda: f"eg-{int(datetime.utcnow().timestamp()*1000)}", index=True, unique=True)
    global_identifier: Optional[str] = Field(default=None, index=True)
    name: str = Field(default="", description="Nom de l'entité géographique")
    status: LocationStatus = LocationStatus.ACTIVE
    mode: LocationMode = LocationMode.INSTANCE
    opening_date: Optional[datetime] = None
    activation_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    deactivation_date: Optional[datetime] = None
    description: Optional[str] = None
    short_name: Optional[str] = None
    address_text: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    address_city: Optional[str] = None
    address_postalcode: Optional[str] = None
    address_country: Optional[str] = "FR"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    physical_type: Optional[LocationPhysicalType] = Field(default=None, description="Type physique de l'entité géographique (site, bâtiment, etc.)")
    type: Optional[str] = None
    responsible_id: Optional[str] = None
    responsible_name: Optional[str] = None
    responsible_firstname: Optional[str] = None
    responsible_email: Optional[str] = None
    responsible_phone: Optional[str] = None
    responsible_rpps: Optional[str] = None
    responsible_adeli: Optional[str] = None
    responsible_specialty: Optional[str] = None
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    finess: Optional[str] = None
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="entite_geographique")
    poles: List["Pole"] = Relationship(back_populates="entite_geo")

class IdentifierNamespace(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = Field(default=None, description="Nom descriptif (ex: 'IPP EJ Principal')", nullable=True)
    system: str
    oid: Optional[str] = None
    type: str
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    prefix_pattern: Optional[str] = Field(default=None)
    prefix_mode: Optional[str] = Field(default="fixed")
    prefix_min: Optional[int] = Field(default=None)
    prefix_max: Optional[int] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    ght_context_id: Optional[int] = Field(default=None, foreign_key="ghtcontext.id")
    ght_context: Optional["GHTContext"] = Relationship(back_populates="namespaces")
    entite_juridique_id: Optional[int] = Field(default=None, foreign_key="entitejuridique.id")
    entite_juridique: Optional["EntiteJuridique"] = Relationship(back_populates="namespaces")
    entite_geographique_id: Optional[int] = Field(default=None, foreign_key="entitegeographique.id")
    entite_geographique: Optional["EntiteGeographique"] = Relationship(back_populates="namespaces")
    pole_id: Optional[int] = Field(default=None, foreign_key="pole.id")
    pole: Optional["Pole"] = Relationship(back_populates="namespaces")
    service_id: Optional[int] = Field(default=None, foreign_key="service.id")
    service: Optional["Service"] = Relationship(back_populates="namespaces")
    unite_fonctionnelle_id: Optional[int] = Field(default=None, foreign_key="unitefonctionnelle.id")
    unite_fonctionnelle: Optional["UniteFonctionnelle"] = Relationship(back_populates="namespaces")
    unite_hebergement_id: Optional[int] = Field(default=None, foreign_key="unitehebergement.id")
    unite_hebergement: Optional["UniteHebergement"] = Relationship(back_populates="namespaces")
    chambre_id: Optional[int] = Field(default=None, foreign_key="chambre.id")
    chambre: Optional["Chambre"] = Relationship(back_populates="namespaces")
    lit_id: Optional[int] = Field(default=None, foreign_key="lit.id")
    lit: Optional["Lit"] = Relationship(back_populates="namespaces")

class LocationStatus(str, Enum):
    """https://hl7.org/fhir/R4/valueset-location-status.html"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"

class LocationMode(str, Enum):
    """https://hl7.org/fhir/R4/valueset-location-mode.html"""
    INSTANCE = "instance"
    KIND = "kind"
    HOSPITALIZATION = "hospitalization"
    AMBULATORY = "ambulatory"
    VIRTUAL = "virtual"

class LocationPhysicalType(str, Enum):
    """http://terminology.hl7.org/ValueSet/location-physical-type + extensions FHIR France"""
    SI = "si"     # Site
    BU = "bu"     # Bâtiment
    WI = "wi"     # Aile (Wing)
    WA = "wa"     # Unité de soins (Ward)
    LV = "lv"     # Niveau/Étage (Level)
    FL = "fl"     # Étage
    RO = "ro"     # Chambre
    BD = "bd"     # Lit
    VE = "ve"     # Véhicule
    HO = "ho"     # Maison/Domicile
    CA = "ca"     # Cabinet
    RD = "rd"     # Route
    AREA = "area" # Zone
    JDN = "jdn"   # Jurisdiction
    # Caractéristiques de chambre selon IHE PAM
    PRESSION_NEGATIVE = "pression_negative"  # Chambre à pression négative
    CARCERAL = "carceral"                    # Chambre carcérale
    CAPITONNE = "capitonne"                  # Chambre capitonnée
    # Types de chambre selon FHIR France
    STANDARD = "standard"                    # Chambre standard
    PRESSION_POSITIVE = "pression_positive"  # Chambre à pression positive
    # Types de location selon FHIR France
    COULOIR = "couloir"                      # Couloir
    BOX = "box"                              # Box
    PLATEAU_TECHNIQUE = "plateau_technique"  # Plateau technique
    POINT_COLLECTE = "point_collecte"        # Point de collecte
    POINT_LIVRAISON = "point_livraison"      # Point de livraison
    SALLE_EXAMEN = "salle_examen"            # Salle d'examen
    SALLE_CONSULTATION = "salle_consultation" # Salle de consultation

class LocationPositionType(str, Enum):
    """Positions dans une chambre selon IHE PAM France"""
    FENETRE = "fenetre"  # Près de la fenêtre
    COULOIR = "couloir"  # Près du couloir
    MILIEU = "milieu"    # Au milieu de la chambre

class MedicalAuthorizationType(str, Enum):
    """Types d'autorisation médicale selon IHE PAM France (codes SAE)"""
    # Autorisations de base (déjà couvertes)
    MEDECINE = "medecine"                    # MDCN
    CHIRURGIE = "chirurgie"                  # CHRG
    GYNECOLOGIE = "gynecologie"              # GNCLG
    PSYCHIATRIE = "psychiatrie"              # PSCHTR
    SOINS_LONGUE_DUREE = "soins_longue_duree" # SN_LNG_DR
    URGENCES = "urgences"                    # MDCN_URGNC

    # Autorisations spécialisées manquantes
    TRAITEMENT_BRULES = "traitement_brules"                    # TRT_BRL
    CHIRURGIE_CARDIAQUE = "chirurgie_cardiaque"                # CHRG_CRDQ
    INTERVENTIONNELLE_CARDIOLOGIE = "interventionnelle_cardiologie"  # ACTVT_IMG_CRDLG
    NEUROCHIRURGIE = "neurochirurgie"                         # NR_CHRG
    INTERVENTIONNELLE_NEURO_RADIOLOGIE = "interventionnelle_neuro_radiologie"  # ACTVT_IMG_NR
    REANIMATION = "reanimation"                               # RNMTN
    EPURATION_RENALE = "epuration_renale"                     # TRT_INSFSNC_RNL_CHRNQ
    AMP_DPN = "amp_dpn"                                       # AMP_DPN
    TRAITEMENT_CANCER = "traitement_cancer"                   # TRT_CNCR
    EXAMENS_GENETIQUES = "examens_genetiques"                 # EXMN_GNTQ

    # SSR spécialisés
    SSR_LOCOMOTEUR = "ssr_locomoteur"                         # SSR_LCMTR
    SSR_NEUROLOGIQUE = "ssr_neurologique"                     # SSR_NRV
    SSR_CARDIOVASCULAIRE = "ssr_cardiovasculaire"             # SSR_CRD
    SSR_RESPIRATOIRE = "ssr_respiratoire"                     # SSR_RSPRTR
    SSR_DIGESTIF = "ssr_digestif"                             # SSR_DGSTF
    SSR_ONCO_HEMATOLOGIQUE = "ssr_onco_hematologique"         # SSR_HMTLGQ
    SSR_BRULES = "ssr_brules"                                 # SSR_BRL
    SSR_ADDICTOLOGIE = "ssr_addictologie"                     # SSR_ADCTV
    SSR_POLYPATHOLOGIQUE = "ssr_polypathologique"             # SSR_PLPTHLGQ

    # Greffes
    GREFFE_REIN = "greffe_rein"                               # GRF_RN
    GREFFE_PANCREAS = "greffe_pancreas"                       # GRF_PNCRS
    GREFFE_REIN_PANCREAS = "greffe_rein_pancreas"             # GRF_RN_PNCRS
    GREFFE_FOIE = "greffe_foie"                               # GRF_F
    GREFFE_INTESTIN = "greffe_intestin"                       # GRF_INTSTN
    GREFFE_COEUR = "greffe_coeur"                             # GRF_CR
    GREFFE_POUmon = "greffe_poumon"                           # GRF_PMN
    GREFFE_COEUR_POUmon = "greffe_coeur_poumon"               # GRF_CR_PMN
    GREFFE_HEMATOPOIETIQUE = "greffe_hematopoietique"         # GRF_HMTPTQ_ALGRF

class LocationServiceType(str, Enum):
    """ValueSet spécifique à la France pour les types de services"""
    MCO = "mco"          # Médecine, Chirurgie, Obstétrique
    SSR = "ssr"          # Soins de Suite et de Réadaptation (notre nomenclature)
    SMR = "smr"          # Soins Médicaux et de Réadaptation (FHIR France)
    PSY = "psy"          # Psychiatrie
    HAD = "had"          # Hospitalisation À Domicile
    EHPAD = "ehpad"      # Établissement d'Hébergement pour Personnes Âgées Dépendantes
    USLD = "usld"        # Unité de Soins Longue Durée (notre nomenclature)
    LG_SJR = "lg_sjr"    # Long séjour (FHIR France)
    MAISON_DE_RETIRE = "maison_de_retire"  # Maison de retraite (distinct d'EHPAD)
    AUTRE = "autre"      # Autre type de structure

class BaseLocation(SQLModel):
    """Classe de base pour tous les types de locations avec champs communs"""
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: str = Field(index=True, unique=True)  # Code (CD)
    global_identifier: Optional[str] = Field(default=None, index=True)  # Identifiant unique global (ID_GLBL)
    name: str  # LBL
    short_name: Optional[str] = None  # LBL_CRT
    description: Optional[str] = None
    status: LocationStatus = LocationStatus.ACTIVE
    mode: LocationMode = LocationMode.INSTANCE
    physical_type: LocationPhysicalType
    
    # Adresse
    address_line1: Optional[str] = None  # ADRS_1
    address_line2: Optional[str] = None  # ADRS_2
    address_line3: Optional[str] = None  # ADRS_3
    address_city: Optional[str] = None  # VL
    address_postalcode: Optional[str] = None  # CD_PSTL
    address_country: Optional[str] = "FR"
    
    # Dates (stockées au format HL7 YYYYMMDD par souci de compatibilité tests)
    opening_date: Optional[str] = None  # DT_OVRTR
    activation_date: Optional[str] = None  # DT_ACTVTN
    closing_date: Optional[str] = None  # DT_FRMTR
    deactivation_date: Optional[str] = None  # DT_FN_ACTVTN



