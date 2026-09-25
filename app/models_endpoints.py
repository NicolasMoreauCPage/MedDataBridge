"""Compatibilité historique des modèles de configuration d'endpoints.

Les modèles sont désormais regroupés dans :mod:`app.models.endpoints`.
"""

from app.models.endpoints import FHIRConfig, FTPConfig, MLLPConfig, MessageLog, SystemEndpoint

__all__ = ["FHIRConfig", "FTPConfig", "MLLPConfig", "MessageLog", "SystemEndpoint"]
