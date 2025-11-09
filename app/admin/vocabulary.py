"""Vues admin pour les vocabulaires"""
from sqladmin import ModelView
from app.models_vocabulary import VocabularySystem, VocabularyValue
from markupsafe import Markup


def format_view_link(model, attribute):
    """Ajoute un lien vers la page de détail complète avec les valeurs"""
    return Markup(f'<a href="/vocabularies/{model.id}" class="btn btn-sm btn-primary" target="_blank"><i class="fa fa-eye"></i> Voir valeurs</a>')


class VocabularySystemAdmin(ModelView, model=VocabularySystem):
    name = "Vocabulary System"
    name_plural = "Vocabulary Systems"
    icon = "fa-solid fa-book"
    column_list = ["id", "name", "label", "system_type", "description", "actions"]
    column_searchable_list = ["name", "label"]
    column_sortable_list = ["id", "name", "system_type"]
    column_default_sort = ("name", False)
    column_details_list = ["id", "name", "label", "uri", "oid", "system_type", "description", "is_user_defined", "created_at"]
    
    # Formatter pour ajouter un lien "Voir les valeurs"
    column_formatters = {
        "actions": format_view_link
    }
    
    # Labels personnalisés
    column_labels = {
        "actions": "Actions"
    }


class VocabularyValueAdmin(ModelView, model=VocabularyValue):
    name = "Vocabulary Value"
    name_plural = "Vocabulary Values"
    icon = "fa-solid fa-list"
    column_list = ["id", "code", "display", "system_id", "order"]
    column_searchable_list = ["code", "display"]
    column_sortable_list = ["id", "code", "order"]
    column_default_sort = ("order", False)
    column_labels = {"system_id": "System"}
    column_details_list = ["id", "system_id", "code", "display", "definition", "is_active", "order", "created_at"]
