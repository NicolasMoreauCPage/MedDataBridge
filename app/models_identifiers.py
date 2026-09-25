"""Compatibilité historique des modèles d'identifiants.

Les modèles sont désormais regroupés dans :mod:`app.models.identifiers`.
"""

from app.models.identifiers import Identifier, IdentifierType

__all__ = ["Identifier", "IdentifierType"]
