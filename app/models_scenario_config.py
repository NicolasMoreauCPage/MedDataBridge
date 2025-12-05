"""Configuration des scénarios par Entité Juridique.

Ce module définit le modèle ScenarioEJConfig qui permet de configurer,
pour chaque EJ, les UF et médecins à utiliser lors de l'exécution des
scénarios d'interopérabilité.

Chaque type de prise en charge (hospitalisation, consultation, urgences)
peut avoir une UF de référence et un médecin associé (numéro RPPS).
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
    medecin_hospitalisation_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour l'hospitalisation"
    )
    medecin_hospitalisation_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour l'hospitalisation (pour affichage)"
    )
    
    # --- UF Consultation externe ---
    uf_consultation_id: Optional[int] = Field(
        default=None,
        foreign_key="unitefonctionnelle.id",
        description="UF pour les consultations externes (A04)"
    )
    medecin_consultation_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour les consultations"
    )
    medecin_consultation_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour les consultations (pour affichage)"
    )
    
    # --- UF Urgences ---
    uf_urgences_id: Optional[int] = Field(
        default=None,
        foreign_key="unitefonctionnelle.id",
        description="UF pour les passages aux urgences"
    )
    medecin_urgences_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour les urgences"
    )
    medecin_urgences_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour les urgences (pour affichage)"
    )
    
    # --- UF Mutation cible (pour transferts A02) ---
    uf_mutation_cible_id: Optional[int] = Field(
        default=None,
        foreign_key="unitefonctionnelle.id",
        description="UF destination pour les mutations/transferts (A02)"
    )
    medecin_mutation_rpps: Optional[str] = Field(
        default=None,
        max_length=11,
        description="Numéro RPPS du médecin pour la mutation"
    )
    medecin_mutation_nom: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du médecin pour la mutation (pour affichage)"
    )
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relations (pour chargement facile des UF)
    # Note: SQLModel ne supporte pas plusieurs FK vers la même table avec Relationship
    # On charge les UF manuellement via les IDs


def get_uf_code_for_event(config: Optional[ScenarioEJConfig], event_type: str, session) -> Optional[str]:
    """Retourne le code UF à utiliser selon le type d'événement.
    
    Args:
        config: Configuration EJ (peut être None)
        event_type: Type d'événement HL7 (A01, A02, A04, etc.)
        session: Session DB pour charger l'UF
        
    Returns:
        Code UF ou None si non configuré
    """
    if not config:
        return None
    
    from app.models_structure import UniteFonctionnelle
    
    uf_id = None
    if event_type in ("A01", "A03", "A11", "A13"):  # Hospitalisation
        uf_id = config.uf_hospitalisation_id
    elif event_type in ("A04", "A05", "A38"):  # Consultation externe
        uf_id = config.uf_consultation_id
    elif event_type in ("A02", "A06", "A07", "A12"):  # Mutation/transfert - UF cible
        uf_id = config.uf_mutation_cible_id
    elif event_type in ("A10",):  # Urgences (si spécifique)
        uf_id = config.uf_urgences_id
    else:
        # Par défaut, utiliser hospitalisation
        uf_id = config.uf_hospitalisation_id
    
    if not uf_id:
        return None
        
    uf = session.get(UniteFonctionnelle, uf_id)
    return uf.identifier if uf else None


def get_medecin_for_event(config: Optional[ScenarioEJConfig], event_type: str) -> Optional[dict]:
    """Retourne les infos médecin à utiliser selon le type d'événement.
    
    Args:
        config: Configuration EJ (peut être None)
        event_type: Type d'événement HL7 (A01, A02, A04, etc.)
        
    Returns:
        Dict avec 'rpps' et 'nom' ou None si non configuré
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
        
    return {"rpps": rpps, "nom": nom or "MEDECIN"}
