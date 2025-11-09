"""Vues admin pour le contexte GHT"""
from sqladmin import ModelView
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique


class GHTContextAdmin(ModelView, model=GHTContext):
    name = "GHT"
    name_plural = "GHTs"
    icon = "fa-solid fa-network-wired"
    column_list = ["id", "name", "code", "description", "is_active", "created_at"]
    column_searchable_list = ["name", "code"]
    column_sortable_list = ["id", "name", "code", "created_at"]
    column_default_sort = ("id", False)
    name_plural = "GHTs"


class EntiteJuridiqueAdmin(ModelView, model=EntiteJuridique):
    name = "Entité Juridique"
    name_plural = "Entités Juridiques"
    icon = "fa-solid fa-landmark"
    column_list = ["id", "name", "short_name", "finess_ej", "ght_context_id", "is_active"]
    column_searchable_list = ["name", "short_name", "finess_ej"]
    column_sortable_list = ["id", "name", "finess_ej"]
    column_default_sort = ("finess_ej", False)
    column_labels = {"ght_context_id": "GHT"}


class EntiteGeographiqueAdmin(ModelView, model=EntiteGeographique):
    name = "Entité Géographique"
    name_plural = "Entités Géographiques"
    icon = "fa-solid fa-map-marker-alt"
    column_list = ["id", "name", "identifier", "finess", "entite_juridique_id", "is_active"]
    column_searchable_list = ["name", "identifier", "finess"]
    column_sortable_list = ["id", "name", "finess"]
    column_default_sort = ("finess", False)
    column_labels = {"entite_juridique_id": "Entité Juridique"}
