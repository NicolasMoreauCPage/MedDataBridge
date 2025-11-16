from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    # Import for type checking only to avoid runtime circular imports
    from app.models_structure_fhir import EntiteGeographique, IdentifierNamespace
else:
    # Only import EntiteGeographique at runtime, not the other structural classes
    from app.models_structure_fhir import EntiteGeographique

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
    __table_args__ = {'extend_existing': True}  # Allow table redefinition for all subclasses
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

class Pole(BaseLocation, table=True):
    """Représente un pôle médical - Équivalent FHIR: Location avec type spécifique"""
    __table_args__ = {'extend_existing': True}  # Allow table redefinition
    # Relations
    entite_geo_id: int = Field(foreign_key="entitegeographique.id")
    entite_geo: "EntiteGeographique" = Relationship(back_populates="poles")
    services: List["Service"] = Relationship(back_populates="pole")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="pole")
    # Virtual marker (créé automatiquement pour combler un saut hiérarchique)
    is_virtual: bool = Field(default=False, index=True)

class Service(BaseLocation, table=True):
    """Représente un service médical - Équivalent FHIR: Location avec servicetype"""
    __table_args__ = {'extend_existing': True}  # Allow table redefinition

    service_type: LocationServiceType
    typology: Optional[str] = None  # TPLG
    
    # Responsable
    responsible_id: Optional[str] = None  # ID_GLBL_RSPNSBL
    responsible_name: Optional[str] = None  # NM_USL_RSPNSBL
    responsible_firstname: Optional[str] = None  # PRNM_RSPNSBL
    responsible_rpps: Optional[str] = None  # RPPS_RSPNSBL
    responsible_adeli: Optional[str] = None  # ADL_RSPNSBL
    responsible_specialty: Optional[str] = None  # CD_SPCLT_RSPNSBL
    
    # Relations
    pole_id: int = Field(foreign_key="pole.id")
    pole: Pole = Relationship(back_populates="services")
    unites_fonctionnelles: List["UniteFonctionnelle"] = Relationship(back_populates="service")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="service")
    # Virtual marker (créé automatiquement pour combler un saut hiérarchique)
    is_virtual: bool = Field(default=False, index=True)


# -- UF Activity modeling (placed before UF to allow link_model class reference) --

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

class UniteFonctionnelle(BaseLocation, table=True):
    """
    Représente une Unité Fonctionnelle (UF) - Équivalent FHIR: FrLocationUf
    https://interop-sante.github.io/hl7.fhir.fr.structure/StructureDefinition-fr-location-uf.html
    """
    um_code: Optional[str] = None  # Code UM
    uf_type: Optional[str] = None  # Typologie UF
    service_id: int = Field(foreign_key="service.id")
    service: Service = Relationship(back_populates="unites_fonctionnelles")
    unites_hebergement: List["UniteHebergement"] = Relationship(back_populates="unite_fonctionnelle")
    # Multi-activité (ex: consultations + hospitalisation + urgences)
    activities: List[UFActivity] = Relationship(
        back_populates="unites_fonctionnelles",
        link_model=UniteFonctionnelleActivityLink,
    )
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="unite_fonctionnelle")
    # Marqueur virtuel (aligné sur Pole/Service) pour UF créées automatiquement
    is_virtual: bool = Field(default=False, index=True)

class UniteHebergement(BaseLocation, table=True):
    """Représente une Unité d'Hébergement (UH)"""
    etage: Optional[str] = None
    aile: Optional[str] = None
    unite_fonctionnelle_id: int = Field(foreign_key="unitefonctionnelle.id")
    unite_fonctionnelle: UniteFonctionnelle = Relationship(back_populates="unites_hebergement")
    chambres: List["Chambre"] = Relationship(back_populates="unite_hebergement")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="unite_hebergement")

class Chambre(BaseLocation, table=True):
    """Représente une chambre"""
    type_chambre: Optional[str] = None
    gender_usage: Optional[str] = None
    unite_hebergement_id: int = Field(foreign_key="unitehebergement.id")
    unite_hebergement: UniteHebergement = Relationship(back_populates="chambres")
    lits: List["Lit"] = Relationship(back_populates="chambre")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="chambre")

class Lit(BaseLocation, table=True):
    """Représente un lit"""
    operational_status: Optional[str] = None  # Statut opérationnel: libre, occupé, maintenance, etc.
    chambre_id: int = Field(foreign_key="chambre.id")
    chambre: Chambre = Relationship(back_populates="lits")
    namespaces: List["IdentifierNamespace"] = Relationship(back_populates="lit")

    # Pydantic v2 migration: remplacer inner Config par model_config
    model_config = {
        "use_enum_values": True
    }

