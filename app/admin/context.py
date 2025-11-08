"""Vues admin pour le contexte GHT"""
from sqladmin import ModelView
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique


class GHTContextAdmin(ModelView, model=GHTContext):
    name = "GHT"
    name_plural = "GHTs"
    icon = "fa-solid fa-network-wired"


class EntiteJuridiqueAdmin(ModelView, model=EntiteJuridique):
    name = "Entité Juridique"
    name_plural = "Entités Juridiques"
    icon = "fa-solid fa-landmark"


class EntiteGeographiqueAdmin(ModelView, model=EntiteGeographique):
    name = "Entité Géographique"
    name_plural = "Entités Géographiques"
    icon = "fa-solid fa-map-marker-alt"
