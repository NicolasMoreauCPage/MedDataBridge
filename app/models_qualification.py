"""Compatibilité : modèles de qualification déplacés vers ``app.models``."""

from app.models.qualification import (
    QualificationCampaign,
    QualificationCampaignItem,
    QualificationCampaignRun,
    ScenarioTargetState,
    ScenarioTheme,
    ScenarioThemeAssignment,
)

__all__ = [
    "QualificationCampaign",
    "QualificationCampaignItem",
    "QualificationCampaignRun",
    "ScenarioTargetState",
    "ScenarioTheme",
    "ScenarioThemeAssignment",
]
