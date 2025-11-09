"""Models de journalisation d'exécution des scénarios.

Permet de tracer chaque exécution (run) et chaque étape émise avec
statut, durée et code d'ACK. Ces modèles servent de base au futur
dashboard de suivi (succès/erreurs, heatmap, filtres).
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


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
    options_json: Optional[str] = Field(default=None, description="JSON des options (start_index, filters, timeplan)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relation vers les logs de steps
    step_logs: list["ScenarioExecutionStepLog"] = Relationship(back_populates="run")


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
    created_at: datetime = Field(default_factory=datetime.utcnow)

    run: ScenarioExecutionRun = Relationship(back_populates="step_logs")
