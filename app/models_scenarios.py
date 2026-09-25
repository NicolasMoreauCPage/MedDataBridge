"""Compatibilité historique des modèles de scénarios.

Les modèles sont désormais regroupés dans :mod:`app.models.scenarios`.
"""

from app.models.scenarios import (
    InteropScenario,
    InteropScenarioStep,
    ScenarioBinding,
    ScenarioTemplate,
    ScenarioTemplateStep,
    ScenarioVersion,
)

__all__ = [
    "InteropScenario",
    "InteropScenarioStep",
    "ScenarioBinding",
    "ScenarioTemplate",
    "ScenarioTemplateStep",
    "ScenarioVersion",
]
