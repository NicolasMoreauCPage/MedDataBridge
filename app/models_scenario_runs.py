"""Compatibilité historique pour les modèles d'exécution de scénarios.

Les modèles sont désormais regroupés dans :mod:`app.models.scenario_runs`.
"""

from app.models.scenario_runs import (
    ScenarioDelivery,
    ScenarioExecutionRun,
    ScenarioExecutionStepLog,
    ScenarioPlay,
    ScenarioPlayStep,
    ScenarioPlayTarget,
)

__all__ = [
    "ScenarioDelivery",
    "ScenarioExecutionRun",
    "ScenarioExecutionStepLog",
    "ScenarioPlay",
    "ScenarioPlayStep",
    "ScenarioPlayTarget",
]
