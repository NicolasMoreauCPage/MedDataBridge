"""Modèles de campagnes de qualification d'interopérabilité."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


class ScenarioTheme(SQLModel, table=True):
    """Thème hiérarchique du catalogue (équivalent des packages historiques)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = Field(default=None, foreign_key="scenariotheme.id", index=True)
    order_index: int = Field(default=0, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioThemeAssignment(SQLModel, table=True):
    """Association non destructive scénario ↔ thème (un scénario peut être transversal)."""

    __table_args__ = (UniqueConstraint("scenario_id", "theme_id", name="uq_scenario_theme_assignment"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    theme_id: int = Field(foreign_key="scenariotheme.id", index=True)
    is_primary: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioTargetState(SQLModel, table=True):
    """État courant d'un scénario pour un logiciel cible logique."""

    __table_args__ = (UniqueConstraint("scenario_id", "target_system_key", name="uq_scenario_target_state"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    target_system_key: str = Field(index=True)
    is_active: bool = Field(default=True, index=True)
    status: str = Field(default="never_run", index=True)  # never_run|success|partial|error
    status_since: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_run_at: Optional[datetime] = Field(default=None, index=True)
    last_success_at: Optional[datetime] = Field(default=None, index=True)
    last_failure_at: Optional[datetime] = Field(default=None, index=True)
    consecutive_failures: int = Field(default=0)
    last_play_id: Optional[int] = Field(default=None, foreign_key="scenarioplay.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class QualificationCampaign(SQLModel, table=True):
    """Une campagne ordonne des scénarios à exécuter contre des partenaires."""

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    name: str
    description: Optional[str] = None
    profile: str = Field(default="IHE_PAM_FR")
    target_system_key: Optional[str] = Field(default=None, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class QualificationCampaignItem(SQLModel, table=True):
    """Un scénario et son endpoint cible dans une campagne."""

    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="qualificationcampaign.id", index=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True)
    endpoint_id: int = Field(foreign_key="systemendpoint.id", index=True)
    order_index: int = Field(default=0, index=True)
    is_active: bool = Field(default=True, index=True)


class QualificationCampaignRun(SQLModel, table=True):
    """Synthèse traçable d'une exécution complète de campagne."""

    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="qualificationcampaign.id", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(default="queued", index=True)  # queued|running|passed|failed|error
    dry_run: bool = Field(default=False, index=True)
    next_item_index: int = Field(default=0)
    total_items: int = 0
    passed_items: int = 0
    failed_items: int = 0
    evidence_json: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
