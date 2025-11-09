"""Vues admin pour les identifiers et namespaces"""
from sqladmin import ModelView
from app.models_identifiers import Identifier
from app.models_structure_fhir import IdentifierNamespace


class IdentifierAdmin(ModelView, model=Identifier):
    name = "Identifier"
    name_plural = "Identifiers"
    icon = "fa-solid fa-fingerprint"
    column_list = ["id", "value", "system", "use", "entity_type", "entity_id"]
    column_searchable_list = ["value", "system"]
    column_sortable_list = ["id", "value", "entity_type"]
    column_default_sort = ("id", True)


class NamespaceAdmin(ModelView, model=IdentifierNamespace):
    name = "Namespace"
    name_plural = "Namespaces"
    icon = "fa-solid fa-tag"
    column_list = ["id", "name", "type", "oid", "system", "ght_context_id", "entite_juridique_id"]
    column_searchable_list = ["name", "type", "oid"]
    column_sortable_list = ["id", "name", "type"]
    column_default_sort = ("type", False)
    column_labels = {"ght_context_id": "GHT", "entite_juridique_id": "EJ"}
