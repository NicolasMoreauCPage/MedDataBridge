from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy.orm import Mapped

if TYPE_CHECKING:  # pragma: no cover
    from app.models import Dossier


class InteropScenario(SQLModel, table=True):
    """Scénario d'interop (suite de messages HL7/FHIR à rejouer)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)  # identifiant stable (ex: path fichier)
    name: str
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, index=True)
    protocol: str = Field(default="HL7")  # HL7 | FHIR | MIXED
    source_path: Optional[str] = None  # emplacement d'origine (documentation/debug)
    tags: Optional[str] = None  # liste séparée par virgules
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    ght_context_id: Optional[int] = Field(default=None, foreign_key="ghtcontext.id")

    # --- Configuration avancée de recalage temporel (date shifting) ---
    time_anchor_mode: Optional[str] = Field(
        default=None,
        description="Mode d'ancrage des dates: 'now' (par défaut), 'admission_minus_days', 'fixed_start'"
    )
    time_anchor_days_offset: Optional[int] = Field(
        default=None,
        description="Si mode 'admission_minus_days': nombre de jours à soustraire depuis maintenant pour fixer l'admission"
    )
    time_fixed_start_iso: Optional[str] = Field(
        default=None,
        description="Timestamp ISO si mode 'fixed_start' (ex: 2025-11-09T08:30:00)"
    )
    preserve_intervals: bool = Field(
        default=True,
        description="Préserve les intervalles relatifs entre événements (delta global + jitter contrôlé)"
    )
    jitter_min_minutes: Optional[int] = Field(
        default=None,
        description="Limite basse jitter (minutes) appliqué aux mouvements non critiques (ex transferts)"
    )
    jitter_max_minutes: Optional[int] = Field(
        default=None,
        description="Limite haute jitter (minutes)"
    )
    apply_jitter_on_events: Optional[str] = Field(
        default="A02,A03,A06,A07,A08",  # transferts / updates
        description="Liste CSV des codes événements HL7 sur lesquels appliquer le jitter"
    )

    steps: Mapped[List["InteropScenarioStep"]] = Relationship(
        back_populates="scenario",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "InteropScenarioStep.order_index"},
    )
    bindings: Mapped[List["ScenarioBinding"]] = Relationship(
        back_populates="scenario",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class InteropScenarioStep(SQLModel, table=True):
    """Étape unique d'un scénario (un message à envoyer)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    order_index: int = Field(index=True)
    name: Optional[str] = None
    description: Optional[str] = None
    message_format: str = Field(default="hl7")  # hl7 | fhir | json | xml
    message_type: Optional[str] = None  # ex: ADT^A28, Bundle
    payload: str = Field(default="", sa_column_kwargs={"nullable": False})
    delay_seconds: Optional[int] = None  # délai suggéré avant envoi suivant
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    scenario: Mapped["InteropScenario"] = Relationship(back_populates="steps")


class ScenarioBinding(SQLModel, table=True):
    """Associe un scénario à un dossier de démonstration."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    dossier_id: int = Field(foreign_key="dossier.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Configuration pour génération d'identifiants de test
    use_test_namespace: bool = Field(
        default=False,
        description="Si vrai, utilise un namespace dédié test pour éviter collisions"
    )
    identifier_prefix_ipp: Optional[str] = Field(
        default=None,
        description="Préfixe spécifique pour IPP (ex: '9001', '91'). Override namespace par défaut."
    )
    identifier_prefix_nda: Optional[str] = Field(
        default=None,
        description="Préfixe spécifique pour NDA (ex: '501', '9'). Override namespace par défaut."
    )
    
    # Identifiants générés lors de la dernière exécution (pour traçabilité)
    generated_ipp: Optional[str] = Field(default=None, description="Dernier IPP généré")
    generated_nda: Optional[str] = Field(default=None, description="Dernier NDA généré")
    generated_venue_id: Optional[str] = Field(default=None, description="Dernier VENUE généré")
    last_execution_at: Optional[datetime] = Field(default=None, description="Date dernière exécution")

    scenario: Mapped["InteropScenario"] = Relationship(back_populates="bindings")
