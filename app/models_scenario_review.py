"""Traçabilité de la revue du catalogue de scénarios."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ScenarioCatalogReview(SQLModel, table=True):
    """Décision de qualification appliquée à un scénario du catalogue.

    Les états sont volontairement distincts de ``InteropScenario.is_active`` :
    l'administrateur garde toujours la possibilité d'activer un scénario pour
    le corriger ou rejouer un test négatif.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="interopscenario.id", index=True, unique=True)
    status: str = Field(default="unassessed", index=True)
    # approved | repairable | manual_review | duplicate | unassessed
    note: Optional[str] = None
    source_report: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
