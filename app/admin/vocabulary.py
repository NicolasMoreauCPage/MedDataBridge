"""Vues admin pour les vocabulaires"""
from sqladmin import ModelView
from app.models_vocabulary import VocabularySystem, VocabularyValue


class VocabularySystemAdmin(ModelView, model=VocabularySystem):
    name = "Vocabulary System"
    name_plural = "Vocabulary Systems"
    icon = "fa-solid fa-book"


class VocabularyValueAdmin(ModelView, model=VocabularyValue):
    name = "Vocabulary Value"
    name_plural = "Vocabulary Values"
    icon = "fa-solid fa-list"
