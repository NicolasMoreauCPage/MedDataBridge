"""Compatibilité historique des modèles de connectivité partagés.

Les modèles sont désormais regroupés dans :mod:`app.models.shared`.
"""

from app.models.shared import EndpointKind, EndpointRole, MessageLog, SystemEndpoint

__all__ = ["EndpointKind", "EndpointRole", "MessageLog", "SystemEndpoint"]
