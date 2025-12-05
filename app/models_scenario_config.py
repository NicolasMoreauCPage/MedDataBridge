"""Configuration des scénarios par Entité Juridique.

Ce module définit le modèle ScenarioEJConfig qui permet de configurer,
pour chaque EJ, les UF et médecins à utiliser lors de l'exécution des
scénarios d'interopérabilité.

Chaque type de prise en charge (hospitalisation, consultation, urgences)
peut avoir une UF de référence et un médecin associé (numéro RPPS).

Conforme IHE PAM France:
- PV1-3 (Hébergement): UF^CHAMBRE^LIT^FACILITY^STATUS
- PV1-7 (Médecin responsable): RPPS^NOM^PRENOM^^^DR^^RPPS^OID^L
- PV1-8 (Médecin adressant/traitant): même format XCN
- ZBE segment obligatoire avec identifiant mouvement
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models_structure import EntiteJuridique, UniteFonctionnelle


class ScenarioEJConfig(SQLModel, table=True):
    """Configuration des UF et médecins pour les scénarios d'une EJ.
    
    Permet de définir les unités fonctionnelles et médecins à utiliser
    lors de l'exécution de scénarios pour une entité juridique donnée.
    Ces valeurs remplacent les placeholders dans les messages HL7/FHIR.
    
    Types de prise en charge:
    - Hospitalisation: admissions A01, séjours complets
    - Consultation externe: A04, consultations ambulatoires  
    - Urgences: passages aux urgences
    - Mutation cible: UF destination pour les transferts A02
    
    Localisation IHE PAM France:
    - PV1-3 format: PointOfCare^Room^Bed^Facility^LocationStatus
    - Chambre et lit optionnels mais recommandés pour conformité
    """
    __tablename__ = "scenario_ej_config"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Lien vers l'EJ
    entite_juridique_id: int = Field(foreign_key="entitejuridique.id", index=True, unique=True)
    
    # --- UF Hospitalisation ---
    uf_hospitalisation_id: Optional[int] = Field(
        default=None, 
        foreign_key="unitefonctionnelle.id",
        description="UF pour les admissions en hospitalisation (A01)"
    )
    chambre_hospitalisation: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Numéro de chambre pour hospitalisation (PV1-3.2)"
    )
    lit_hospitalisation: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Numéro de lit pour hospitalisation (PV1-3.3)"
    )
    medecin_hospitalisation_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour l'hospitalisation"
    )
    medecin_hospitalisation_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour l'hospitalisation (format: NOM Prénom)"
    )
    
    # --- UF Consultation externe ---
    uf_consultation_id: Optional[int] = Field(
        default=None,
        foreign_key="unitefonctionnelle.id",
        description="UF pour les consultations externes (A04)"
    )
    chambre_consultation: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Salle de consultation (PV1-3.2)"
    )
    medecin_consultation_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour les consultations"
    )
    medecin_consultation_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour les consultations (format: NOM Prénom)"
    )
    
    # --- UF Urgences ---
    uf_urgences_id: Optional[int] = Field(
        default=None,
        foreign_key="unitefonctionnelle.id",
        description="UF pour les passages aux urgences"
    )
    chambre_urgences: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Box urgences (PV1-3.2)"
    )
    lit_urgences: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Brancard/lit urgences (PV1-3.3)"
    )
    medecin_urgences_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour les urgences"
    )
    medecin_urgences_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour les urgences (format: NOM Prénom)"
    )
    
    # --- UF Mutation cible (pour transferts A02) ---
    uf_mutation_cible_id: Optional[int] = Field(
        default=None,
        foreign_key="unitefonctionnelle.id",
        description="UF destination pour les mutations/transferts (A02)"
    )
    chambre_mutation: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Chambre destination mutation (PV1-3.2)"
    )
    lit_mutation: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Lit destination mutation (PV1-3.3)"
    )
    medecin_mutation_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour la mutation"
    )
    medecin_mutation_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour la mutation (format: NOM Prénom)"
    )
    
    # --- Médecin traitant (PV1-8) ---
    medecin_traitant_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin traitant/adressant (PV1-8)"
    )
    medecin_traitant_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin traitant (format: NOM Prénom)"
    )
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relations (pour chargement facile des UF)
    # Note: SQLModel ne supporte pas plusieurs FK vers la même table avec Relationship
    # On charge les UF manuellement via les IDs


# OID officiel pour les identifiants RPPS en France
OID_RPPS = "1.2.250.1.71.4.2.1"


def get_location_for_event(
    config: Optional["ScenarioEJConfig"], 
    event_type: str, 
    session,
    facility_code: Optional[str] = None
) -> dict:
    """Retourne les informations de localisation pour PV1-3.
    
    Format IHE PAM France PV1-3 (PL - Patient Location):
    PointOfCare^Room^Bed^Facility^LocationStatus^PersonLocationType^Building^Floor^LocationDescription^ComprehensiveLocId
    
    Args:
        config: Configuration EJ (peut être None)
        event_type: Type d'événement HL7 (A01, A02, A04, etc.)
        session: Session DB pour charger l'UF
        facility_code: Code établissement (optionnel)
        
    Returns:
        Dict avec 'uf_code', 'room', 'bed', 'pv1_3' formaté
    """
    from app.models_structure import UniteFonctionnelle
    
    result = {
        "uf_code": None,
        "room": None,
        "bed": None,
        "pv1_3": "^^^"  # Valeur par défaut vide
    }
    
    if not config:
        return result
    
    uf_id = None
    room = None
    bed = None
    
    if event_type in ("A01", "A03", "A11", "A13"):  # Hospitalisation
        uf_id = config.uf_hospitalisation_id
        room = config.chambre_hospitalisation
        bed = config.lit_hospitalisation
    elif event_type in ("A04", "A05", "A38"):  # Consultation externe
        uf_id = config.uf_consultation_id
        room = config.chambre_consultation
        bed = None  # Pas de lit en consultation
    elif event_type in ("A02", "A06", "A07", "A12"):  # Mutation/transfert - UF cible
        uf_id = config.uf_mutation_cible_id
        room = config.chambre_mutation
        bed = config.lit_mutation
    elif event_type in ("A10",):  # Urgences
        uf_id = config.uf_urgences_id
        room = config.chambre_urgences
        bed = config.lit_urgences
    else:
        # Par défaut, utiliser hospitalisation
        uf_id = config.uf_hospitalisation_id
        room = config.chambre_hospitalisation
        bed = config.lit_hospitalisation
    
    if not uf_id:
        return result
        
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return result
    
    uf_code = uf.identifier or uf.name or "UF"
    result["uf_code"] = uf_code
    result["room"] = room or ""
    result["bed"] = bed or ""
    
    # Format PV1-3: PointOfCare^Room^Bed^Facility^LocationStatus
    facility = facility_code or uf_code
    location_status = "ACTIVE"
    result["pv1_3"] = f"{uf_code}^{room or ''}^{bed or ''}^{facility}^{location_status}"
    
    return result


def _parse_medecin_name(rpps: str, nom: Optional[str]) -> dict:
    """Parse le nom du médecin pour extraire nom de famille et prénom.
    
    Gère les formats:
    - "DURAND Pierre"
    - "Dr DURAND Pierre"
    - "DURAND"
    - "Dr. DURAND Pierre"
    
    Args:
        rpps: Numéro RPPS
        nom: Nom complet (peut contenir "Dr" ou "Dr.")
        
    Returns:
        Dict avec 'rpps', 'nom', 'prenom'
    """
    if not nom:
        return {"rpps": rpps, "nom": "MEDECIN", "prenom": ""}
    
    # Nettoyer et normaliser
    nom_clean = nom.strip()
    
    # Retirer les préfixes Dr. ou Dr
    if nom_clean.lower().startswith("dr."):
        nom_clean = nom_clean[3:].strip()
    elif nom_clean.lower().startswith("dr "):
        nom_clean = nom_clean[3:].strip()
    
    # Parser NOM Prénom
    parts = nom_clean.split(maxsplit=1)
    family = parts[0].upper() if parts else "MEDECIN"
    given = parts[1] if len(parts) > 1 else ""
    
    return {"rpps": rpps, "nom": family, "prenom": given}


def get_uf_code_for_event(config: Optional["ScenarioEJConfig"], event_type: str, session) -> Optional[str]:
    """Retourne le code UF à utiliser selon le type d'événement.
    
    Args:
        config: Configuration EJ (peut être None)
        event_type: Type d'événement HL7 (A01, A02, A04, etc.)
        session: Session DB pour charger l'UF
        
    Returns:
        Code UF ou None si non configuré
    """
    location = get_location_for_event(config, event_type, session)
    return location.get("uf_code")


def get_medecin_for_event(config: Optional["ScenarioEJConfig"], event_type: str) -> Optional[dict]:
    """Retourne les infos médecin responsable à utiliser selon le type d'événement.
    
    Args:
        config: Configuration EJ (peut être None)
        event_type: Type d'événement HL7 (A01, A02, A04, etc.)
        
    Returns:
        Dict avec 'rpps', 'nom', 'prenom' ou None si non configuré
    """
    if not config:
        return None
    
    rpps, nom = None, None
    if event_type in ("A01", "A03", "A11", "A13"):  # Hospitalisation
        rpps = config.medecin_hospitalisation_rpps
        nom = config.medecin_hospitalisation_nom
    elif event_type in ("A04", "A05", "A38"):  # Consultation externe
        rpps = config.medecin_consultation_rpps
        nom = config.medecin_consultation_nom
    elif event_type in ("A02", "A06", "A07", "A12"):  # Mutation/transfert
        rpps = config.medecin_mutation_rpps
        nom = config.medecin_mutation_nom
    elif event_type in ("A10",):  # Urgences
        rpps = config.medecin_urgences_rpps
        nom = config.medecin_urgences_nom
    else:
        # Par défaut, utiliser hospitalisation
        rpps = config.medecin_hospitalisation_rpps
        nom = config.medecin_hospitalisation_nom
    
    if not rpps:
        return None
    
    return _parse_medecin_name(rpps, nom)


def get_medecin_traitant(config: Optional["ScenarioEJConfig"]) -> Optional[dict]:
    """Retourne les infos du médecin traitant pour PV1-8.
    
    Args:
        config: Configuration EJ (peut être None)
        
    Returns:
        Dict avec 'rpps', 'nom', 'prenom' ou None si non configuré
    """
    if not config or not config.medecin_traitant_rpps:
        return None
    
    return _parse_medecin_name(config.medecin_traitant_rpps, config.medecin_traitant_nom)


def build_xcn_field(medecin_info: Optional[dict], id_type: str = "RPPS") -> str:
    """Construit un champ XCN conforme IHE PAM France.
    
    Format XCN (Extended Composite ID Number and Name for Persons):
    ID^FamilyName^GivenName^MiddleName^Suffix^Prefix^Degree^SourceTable^AssigningAuthority^NameTypeCode^IDCheckDigit
    
    Pour un médecin identifié par RPPS:
    - ID = numéro RPPS
    - SourceTable = RPPS
    - AssigningAuthority = OID RPPS (1.2.250.1.71.4.2.1)
    - NameTypeCode = L (Legal)
    
    Args:
        medecin_info: Dict avec 'rpps', 'nom', 'prenom'
        id_type: Type d'identifiant (RPPS par défaut)
        
    Returns:
        Champ XCN formaté
    """
    if not medecin_info or not medecin_info.get("rpps"):
        return ""
    
    rpps = medecin_info.get("rpps", "")
    family = medecin_info.get("nom", "MEDECIN")
    given = medecin_info.get("prenom", "")
    
    # Format: ID^Family^Given^^Suffix^Prefix^Degree^SourceTable^AssigningAuth^NameType
    # Les ^ vides sont des placeholders pour Middle, Suffix
    return f"{rpps}^{family}^{given}^^^Dr.^^{id_type}^{OID_RPPS}^L"
