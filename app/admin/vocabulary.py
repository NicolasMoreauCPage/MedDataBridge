"""Vues admin pour les vocabulaires"""
from sqladmin import ModelView
from app.models_vocabulary import VocabularySystem, VocabularyValue


class VocabularySystemAdmin(ModelView, model=VocabularySystem):
    name = "Vocabulary System"
    name_plural = "Vocabulary Systems"
    icon = "fa-solid fa-book"
    column_list = ["id", "name", "label", "system_type", "description"]
    column_searchable_list = ["name", "label"]
    column_sortable_list = ["id", "name", "system_type"]
    column_default_sort = ("name", False)


class VocabularyValueAdmin(ModelView, model=VocabularyValue):
    name = "Vocabulary Value"
    name_plural = "Vocabulary Values"
    icon = "fa-solid fa-list"
    column_list = ["id", "code", "display", "vocabulary_system_id", "order"]
    column_searchable_list = ["code", "display"]
    column_sortable_list = ["id", "code", "order"]
    column_default_sort = ("order", False)
    column_labels = {"vocabulary_system_id": "System"}
