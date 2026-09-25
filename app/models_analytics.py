"""Compatibilité historique des modèles d'analytics.

Les modèles sont désormais regroupés dans :mod:`app.models.analytics`.
"""

from app.models.analytics import (
    AlertRule,
    AlertSeverity,
    AlertType,
    CapacityByServiceResponse,
    CapacityByUmResponse,
    ComputedAlert,
    KpiResponse,
    OccupationSnapshot,
)

__all__ = [
    "AlertRule",
    "AlertSeverity",
    "AlertType",
    "CapacityByServiceResponse",
    "CapacityByUmResponse",
    "ComputedAlert",
    "KpiResponse",
    "OccupationSnapshot",
]
