"""Vues admin pour les identifiers et namespaces"""
from sqladmin import ModelView
from app.models_identifiers import Identifier
from app.models_structure_fhir import IdentifierNamespace


class IdentifierAdmin(ModelView, model=Identifier):
    name = "Identifier"
    name_plural = "Identifiers"
    icon = "fa-solid fa-fingerprint"


class NamespaceAdmin(ModelView, model=IdentifierNamespace):
    name = "Namespace"
    name_plural = "Namespaces"
    icon = "fa-solid fa-tag"
