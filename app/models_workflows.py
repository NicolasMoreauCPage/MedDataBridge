"""Compatibilité historique des modèles de workflows.

Les modèles sont désormais regroupés dans :mod:`app.models.workflows`.
"""

from app.models.workflows import (
    ActionType,
    EntityType,
    ExecutionStatus,
    ScenarioType,
    WorkflowExecutionStep,
    WorkflowScenario,
    WorkflowScenarioExecution,
    WorkflowScenarioStep,
)

__all__ = [
    "ActionType",
    "EntityType",
    "ExecutionStatus",
    "ScenarioType",
    "WorkflowExecutionStep",
    "WorkflowScenario",
    "WorkflowScenarioExecution",
    "WorkflowScenarioStep",
]
