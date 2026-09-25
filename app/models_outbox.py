"""Compatibilité : modèles d'outbox déplacés vers ``app.models.outbox``."""

from app.models.outbox import OutboundMessage

__all__ = ["OutboundMessage"]
