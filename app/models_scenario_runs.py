"""Models de journalisation d'exécution des scénarios.

Permet de tracer chaque exécution (run) et chaque étape émise avec
statut, durée et code d'ACK. Ces modèles servent de base au futur
dashboard de suivi (succès/erreurs, heatmap, filtres).
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint


class ScenarioPlay(SQLModel, table=True):
    """Un jeu immuable d'un scénario, partagé par toutes ses cibles.

    Contrairement à ``ScenarioExecutionRun`` (historique par endpoint), un play
    porte les identifiants créés une seule fois et les payloads réellement
    compilés. Il rend un rejeu multi-protocoles traçable et non destructif pour
    le système destinataire.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    scenario_version_id: Optional[int] = Field(default=None, foreign_key="scenarioversion.id", index=True)
    play_key: str = Field(index=True, unique=True)
    ght_context_id: Optional[int] = Field(default=None, foreign_key="ghtcontext.id", index=True)
    status: str = Field(default="prepared", index=True)  # prepared|running|success|partial|error|dry_run
    dry_run: bool = Field(default=False, index=True)
    identity_json: str = Field(default="{}", description="Identité et identifiants alloués à ce jeu")
    options_json: Optional[str] = Field(default=None)
    error_policy: str = Field(default="continue_other_targets", index=True)
    result_json: Optional[str] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None, index=True)
    finished_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioPlayTarget(SQLModel, table=True):
    """Cible sélectionnée pour un jeu, avec un nom de système logique."""

    __table_args__ = (UniqueConstraint("play_id", "endpoint_id", name="uq_scenario_play_target"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    play_id: int = Field(foreign_key="scenarioplay.id", index=True)
    endpoint_id: int = Field(foreign_key="systemendpoint.id", index=True)
    target_system_key: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioPlayStep(SQLModel, table=True):
    """Instantané compilé d'une étape, avant toute émission."""

    __table_args__ = (UniqueConstraint("play_id", "order_index", name="uq_scenario_play_step_order"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    play_id: int = Field(foreign_key="scenarioplay.id", index=True)
    scenario_step_id: Optional[int] = Field(default=None, foreign_key="interopscenariostep.id", index=True)
    order_index: int = Field(index=True)
    name: Optional[str] = None
    message_format: str = Field(index=True)
    message_type: Optional[str] = None
    source_payload: str
    compiled_payload: str
    routing_json: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioDelivery(SQLModel, table=True):
    """Livraison d'une étape compilée vers une cible précise."""

    __table_args__ = (UniqueConstraint("play_step_id", "endpoint_id", name="uq_scenario_delivery_step_endpoint"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    play_id: int = Field(foreign_key="scenarioplay.id", index=True)
    play_step_id: int = Field(foreign_key="scenarioplaystep.id", index=True)
    endpoint_id: int = Field(foreign_key="systemendpoint.id", index=True)
    status: str = Field(default="pending", index=True)  # queued|pending|sent|retry|error|blocked|skipped|dry_run
    transport: Optional[str] = Field(default=None, index=True)
    ack_code: Optional[str] = Field(default=None)
    response_payload: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    message_log_id: Optional[int] = Field(default=None, foreign_key="messagelog.id", index=True)
    outbox_id: Optional[int] = Field(default=None, foreign_key="outboundmessage.id", index=True)
    # Chaque cible peut recevoir une projection UF/médecin différente. Cette
    # copie immuable est la source de vérité de l'outbox et des rejeux.
    compiled_payload: Optional[str] = Field(default=None)
    target_context_json: Optional[str] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioExecutionRun(SQLModel, table=True):
    """Représente une exécution d'un scénario sur un endpoint (ou plusieurs).

    Un run correspond à l'envoi séquentiel (ou dry-run) d'un ensemble d'étapes.
    Pour un envoi multi-endpoints, on crée un run par endpoint.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    endpoint_id: Optional[int] = Field(default=None, foreign_key="systemendpoint.id", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(default="running", index=True)  # running|success|partial|error|dry_run
    total_steps: int = 0
    success_steps: int = 0
    error_steps: int = 0
    skipped_steps: int = 0
    dry_run: bool = Field(default=False, index=True)
    qualification_verdict: str = Field(default="not_evaluated", index=True)  # passed|failed|error|not_evaluated
    assertion_total: int = 0
    assertion_passed: int = 0
    evidence_json: Optional[str] = Field(default=None, description="Résultats des assertions JSON")
    options_json: Optional[str] = Field(default=None, description="JSON des options (start_index, filters, timeplan)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relation vers les logs de Étape
    step_logs: list["ScenarioExecutionStepLog"] = Relationship(back_populates="run")

    @property
    def duration_seconds(self) -> Optional[float]:
        """Retourne la durée du run en secondes quand fini."""
        if not self.finished_at:
            return None
        return max((self.finished_at - self.started_at).total_seconds(), 0.0)


class ScenarioExecutionStepLog(SQLModel, table=True):
    """Journalisation fine d'une étape pendant un run."""

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="scenarioexecutionrun.id", index=True)
    step_id: Optional[int] = Field(default=None, foreign_key="interopscenariostep.id", index=True)
    endpoint_id: Optional[int] = Field(default=None, foreign_key="systemendpoint.id", index=True)
    order_index: Optional[int] = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)  # sent|skipped|error|dry_run
    ack_code: Optional[str] = Field(default=None, index=True)  # AA|AE|AR|HTTP code
    duration_ms: Optional[int] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    payload_excerpt: Optional[str] = Field(default=None, description="Extrait du message (début) limité pour dashboard")
    assertion_results_json: Optional[str] = Field(default=None, description="Résultats d'assertions de l'étape")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    run: ScenarioExecutionRun = Relationship(back_populates="step_logs")

    @property
    def step_order(self) -> Optional[int]:
        """Expose order_index sous un nom plus lisible pour le dashboard."""
        return self.order_index

    @property
    def duration_seconds(self) -> Optional[float]:
        """Convertit la durée enregistrée en millisecondes vers les secondes."""
        if self.duration_ms is None:
            return None
        return max(self.duration_ms / 1000.0, 0.0)

    @property
    def error_detail(self) -> Optional[str]:
        """Alias utilisé par la vue dashboard pour accéder au message d'erreur."""
        return self.error_message
