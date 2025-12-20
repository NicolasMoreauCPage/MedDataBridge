# app/models/hprim_models.py
"""
Modèles de données pour le système HPRIM XML 2.4
Conformément aux spécifications HPRIM XML pour la cotation des actes médicaux
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from enum import Enum


class HprimMessageType(Enum):
    """Types de messages HPRIM"""
    EVENEMENTS_SERVEUR_ACTES = "evenementsServeurActes"
    ACQUITTEMENTS_SERVEUR_ACTES = "acquittementsServeurActes"


class HprimAction(Enum):
    """Actions possibles sur les entités HPRIM"""
    CREATION = "création"
    MODIFICATION = "modification"
    SUPPRESSION = "suppression"
    INFORMATION = "information"


class HprimCivilite(Enum):
    """Civilités HPRIM"""
    MONSIEUR = "mr"
    MADAME = "mme"
    MADEMOISELLE = "mlle"
    DOCTEUR = "dr"
    PROFESSEUR = "pr"


@dataclass
class HprimEnteteMessage:
    """En-tête de message HPRIM"""
    emetteur_id: str
    emetteur_nom: str
    destinataire_id: str
    destinataire_nom: str
    date_emission: datetime
    message_id: str
    message_type: HprimMessageType


@dataclass
class HprimPatient:
    """Informations patient (format light HPRIM)"""
    identifiant_id: str
    identifiant_clef: str
    nom: str
    prenom: str
    date_naissance: Optional[str] = None
    sexe: Optional[str] = None
    civilite: Optional[HprimCivilite] = None


@dataclass
class HprimAdresse:
    """Adresse HPRIM"""
    ligne1: Optional[str] = None
    ligne2: Optional[str] = None
    code_postal: Optional[str] = None
    ville: Optional[str] = None
    pays: str = "FRANCE"


@dataclass
class HprimProfessionnel:
    """Professionnel de santé HPRIM"""
    nom: str
    prenom: str
    numero_rpps: str
    specialite: Optional[str] = None
    civilite: Optional[HprimCivilite] = None
    adresse: Optional[HprimAdresse] = None


@dataclass
class HprimEntiteJuridique:
    """Entité juridique HPRIM"""
    libelle: str
    finess: Optional[str] = None
    adresse: Optional[HprimAdresse] = None


@dataclass
class HprimVenue:
    """Venue (lieu de soins) HPRIM"""
    identifiant: str
    libelle: str
    entite_juridique: Optional[HprimEntiteJuridique] = None


@dataclass
class HprimModificateur:
    """Modificateur CCAM"""
    code: str  # A-Z, 0-9
    statut: str = "nft"  # nft (non facturé), etc.


@dataclass
class HprimPriseCharge:
    """Prise en charge HPRIM"""
    risque: Optional[str] = None
    date_demande_accord: Optional[str] = None
    entente_prealable: Optional[str] = None
    indicateur_parcours_soins: Optional[str] = None


@dataclass
class HprimMontant:
    """Montant HPRIM"""
    valeur: Decimal
    devise: str = "EUR"


@dataclass
class HprimActeCCAM:
    """Acte CCAM complet"""
    identifiant: str
    code_acte: str  # Format: AAAA999
    code_activite: str  # 2 chiffres
    code_phase: str  # 2 chiffres
    execute_date: datetime
    executant: HprimProfessionnel
    code_acte_extension_pmsi: Optional[str] = None  # Format: 99
    execute_heure: Optional[str] = None
    modificateurs: List[HprimModificateur] = field(default_factory=list)
    quantite: int = 1
    montant: Optional[HprimMontant] = None
    commentaire: Optional[str] = None
    prise_charge: Optional[HprimPriseCharge] = None
    identifiant_acte_principal: Optional[str] = None
    facture_realisation: Optional[HprimMontant] = None
    radiotherapie: Optional[Dict[str, Any]] = None
    extension_temporaires: Optional[Dict[str, Any]] = None

    # Attributs
    action: HprimAction = HprimAction.CREATION
    facturable: bool = True
    valide: bool = False
    facture: bool = False
    remboursement_exceptionnel: bool = False
    gratuit: bool = False
    option_coordination: bool = False
    top_prevention_amo_amc: bool = False
    exoneration_ccam: Optional[str] = None
    rapport_exoneration: Optional[str] = None
    supplement_charges: Optional[str] = None
    forfait_securite_environnement_hospitalier: Optional[str] = None
    signe: bool = False
    pmsi: Optional[str] = None
    documentaire: bool = False

    def __post_init__(self):
        """Validation post-initialisation"""
        if not self.code_acte or len(self.code_acte) != 7:
            raise ValueError(f"Code acte CCAM invalide: {self.code_acte}")
        if not self.code_activite or len(self.code_activite) != 2:
            raise ValueError(f"Code activité invalide: {self.code_activite}")
        if not self.code_phase or len(self.code_phase) != 2:
            raise ValueError(f"Code phase invalide: {self.code_phase}")


@dataclass
class HprimActeNGAP:
    """Acte NGAP"""
    identifiant: str
    lettre_cle: str  # A-Z
    coefficient: Decimal
    execute_date: datetime
    prestataire: HprimProfessionnel
    denombrement: Optional[int] = None
    position_dentaire: Optional[str] = None
    execute_heure: Optional[str] = None
    numero_seance: Optional[int] = None
    nabms: List[int] = field(default_factory=list)
    minor_major: Optional[str] = None
    montant: Optional[HprimMontant] = None
    commentaire: Optional[str] = None
    bhn_phns: Optional[Dict[str, Any]] = None
    facture_realisation: Optional[HprimMontant] = None
    extension_temporaires: Optional[Dict[str, Any]] = None
    prise_charge: Optional[HprimPriseCharge] = None

    # Attributs
    action: HprimAction = HprimAction.CREATION
    facturable: bool = True
    valide: bool = False
    facture: bool = False
    execution_nuit: bool = False
    execution_dimanche_jour_ferie: bool = False
    acte_hors_nomenclature: bool = False
    gratuit: bool = False
    portee_cle: str = "n"
    activite_recherche: bool = False
    code_prestation: Optional[str] = None
    rapport_exoneration: Optional[str] = None


@dataclass
class HprimCodeLPP:
    """Code LPP avec portee"""
    code: str  # 13 chiffres
    portee: str = "n"


@dataclass
class HprimLPP:
    """LPP (Lettre Clé de Pathologie Professionnelle)"""
    code: HprimCodeLPP
    prix_unitaire: Decimal
    montant_total: Decimal
    libelle: Optional[str] = None
    quantite: int = 1


@dataclass
class HprimActeLPP:
    """Acte LPP"""
    identifiant: str
    intervention: Optional[Dict[str, Any]] = None
    demande: Optional[Dict[str, Any]] = None
    lpps: List[HprimLPP] = field(default_factory=list)


@dataclass
class HprimUCD:
    """UCD (Unité Commune de Dispensation)"""
    code: str  # Code CIP-13
    designation: str
    quantite: int
    prix_unitaire: Decimal
    montant_total: Decimal


@dataclass
class HprimActeUCD:
    """Acte UCD"""
    identifiant: str
    intervention: Optional[Dict[str, Any]] = None
    demande: Optional[Dict[str, Any]] = None
    ucds: List[HprimUCD] = field(default_factory=list)


@dataclass
class HprimIntervention:
    """Intervention médicale HPRIM"""
    identifiant: str
    libelle: str
    date_intervention: datetime
    medecin: HprimProfessionnel
    acte_principal: Optional[HprimActeCCAM] = None
    actes_lies: List[HprimActeCCAM] = field(default_factory=list)


@dataclass
class HprimAcquittement:
    """Acquittement HPRIM"""
    statut: str  # OK, ERREUR, etc.
    message_id_original: str
    date_acquittement: datetime
    erreurs: List[Dict[str, Any]] = field(default_factory=list)
    avertissements: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HprimMessage:
    """Message HPRIM complet"""
    entete: HprimEnteteMessage
    patient: HprimPatient
    acteur: HprimProfessionnel
    venue: Optional[HprimVenue] = None

    # Contenu selon le type
    interventions: List[HprimIntervention] = field(default_factory=list)
    actes_ccam: List[HprimActeCCAM] = field(default_factory=list)
    actes_ngap: List[HprimActeNGAP] = field(default_factory=list)
    actes_lpp: Optional[HprimActeLPP] = None
    actes_ucd: Optional[HprimActeUCD] = None

    # Métadonnées
    version: str = "2.4"
    acquittement_attendu: bool = True
    identifiant_attendu: bool = False
    realise: bool = True
    interrogation: bool = False

    # Acquittement (si réponse)
    acquittement: Optional[HprimAcquittement] = None


# Types pour la validation
HprimActeType = Union[HprimActeCCAM, HprimActeNGAP, HprimActeLPP, HprimActeUCD]
HprimMessageContent = Union[HprimIntervention, HprimActeType]