"""Vues admin pour la structure hospitalière"""
from sqladmin import ModelView
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit, UFActivity


class PoleAdmin(ModelView, model=Pole):
    name = "Pôle"
    name_plural = "Pôles"
    icon = "fa-solid fa-building"
    column_list = ["id", "name", "identifier", "entite_geo_id", "status"]
    column_searchable_list = ["name", "identifier"]
    column_sortable_list = ["id", "name", "identifier"]
    column_labels = {"entite_geo_id": "Entité Géo"}


class ServiceAdmin(ModelView, model=Service):
    name = "Service"
    name_plural = "Services"
    icon = "fa-solid fa-hospital"
    column_list = ["id", "name", "identifier", "pole_id", "service_type", "status"]
    column_searchable_list = ["name", "identifier"]
    column_sortable_list = ["id", "name", "identifier"]
    column_labels = {"pole_id": "Pôle"}


class UniteFonctionnelleAdmin(ModelView, model=UniteFonctionnelle):
    name = "Unité Fonctionnelle"
    name_plural = "Unités Fonctionnelles"
    icon = "fa-solid fa-sitemap"
    column_list = ["id", "name", "identifier", "um_code", "service_id", "status"]
    column_searchable_list = ["name", "identifier", "um_code"]
    column_sortable_list = ["id", "name", "identifier"]
    column_labels = {"service_id": "Service"}


class UFActivityAdmin(ModelView, model=UFActivity):
    name = "UFActivity"
    name_plural = "UFActivities"
    icon = "fa-solid fa-chart-line"
    column_list = ["id", "code", "display"]
    column_searchable_list = ["code", "display"]
    column_sortable_list = ["code"]


class UniteHebergementAdmin(ModelView, model=UniteHebergement):
    name = "Unité d'Hébergement"
    name_plural = "Unités d'Hébergement"
    icon = "fa-solid fa-home"
    column_list = ["id", "name", "identifier", "unite_fonctionnelle_id", "status"]
    column_searchable_list = ["name", "identifier"]
    column_sortable_list = ["id", "name"]
    column_labels = {"unite_fonctionnelle_id": "UF"}


class ChambreAdmin(ModelView, model=Chambre):
    name = "Chambre"
    name_plural = "Chambres"
    icon = "fa-solid fa-door-closed"
    column_list = ["id", "name", "identifier", "unite_hebergement_id", "type_chambre", "status"]
    column_searchable_list = ["name", "identifier"]
    column_sortable_list = ["id", "name"]
    column_labels = {"unite_hebergement_id": "UH"}


class LitAdmin(ModelView, model=Lit):
    name = "Lit"
    name_plural = "Lits"
    icon = "fa-solid fa-bed"
    column_list = ["id", "name", "identifier", "chambre_id", "operational_status"]
    column_searchable_list = ["name", "identifier"]
    column_sortable_list = ["id", "name"]
    column_labels = {"chambre_id": "Chambre"}
