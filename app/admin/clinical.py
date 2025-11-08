"""Vues admin pour les entités cliniques (Patient, Dossier, Venue, Mouvement)"""
from sqladmin import ModelView
from app.models import Patient, Dossier, Venue, Mouvement


class PatientAdmin(ModelView, model=Patient):
    name = "Patient"
    name_plural = "Patients"
    icon = "fa-solid fa-user"


class DossierAdmin(ModelView, model=Dossier):
    name = "Dossier"
    name_plural = "Dossiers"
    icon = "fa-solid fa-folder"


class VenueAdmin(ModelView, model=Venue):
    name = "Venue"
    name_plural = "Venues"
    icon = "fa-solid fa-bed"


class MouvementAdmin(ModelView, model=Mouvement):
    name = "Mouvement"
    name_plural = "Mouvements"
    icon = "fa-solid fa-arrows-alt"
