"""Vues admin pour la structure hospitalière"""
from sqladmin import ModelView
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit, UFActivity


class PoleAdmin(ModelView, model=Pole):
    name = "Pôle"
    name_plural = "Pôles"
    icon = "fa-solid fa-building"


class ServiceAdmin(ModelView, model=Service):
    name = "Service"
    name_plural = "Services"
    icon = "fa-solid fa-hospital"


class UniteFonctionnelleAdmin(ModelView, model=UniteFonctionnelle):
    name = "Unité Fonctionnelle"
    name_plural = "Unités Fonctionnelles"
    icon = "fa-solid fa-sitemap"


class UFActivityAdmin(ModelView, model=UFActivity):
    name = "UFActivity"
    name_plural = "UFActivities"
    icon = "fa-solid fa-chart-line"


class UniteHebergementAdmin(ModelView, model=UniteHebergement):
    name = "Unité d'Hébergement"
    name_plural = "Unités d'Hébergement"
    icon = "fa-solid fa-home"


class ChambreAdmin(ModelView, model=Chambre):
    name = "Chambre"
    name_plural = "Chambres"
    icon = "fa-solid fa-door-closed"


class LitAdmin(ModelView, model=Lit):
    name = "Lit"
    name_plural = "Lits"
    icon = "fa-solid fa-bed"
