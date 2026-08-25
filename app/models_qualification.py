"""Modèles de campagnes de qualification d'interopérabilité."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class QualificationCampaign(SQLModel, table=True):
    """Une campagne ordonne des scénarios à exécuter contre des partenaires."""

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    name: str
    description: Optional[str] = None
    profile: str = Field(default="IHE_PAM_FR")
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
    status: str = Field(default="running", index=True)  # passed|failed|error
    total_items: int = 0
    passed_items: int = 0
    failed_items: int = 0
    evidence_json: Optional[str] = None
