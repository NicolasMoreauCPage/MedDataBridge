"""Compatibilité : modèles de vocabulaire déplacés vers ``app.models``."""

from app.models.vocabulary import VocabularyMapping, VocabularySystem, VocabularySystemType, VocabularyValue

__all__ = ["VocabularyMapping", "VocabularySystem", "VocabularySystemType", "VocabularyValue"]
