"""Vues admin pour les entités cliniques (Patient, Dossier, Venue, Mouvement)"""
from sqladmin import ModelView
from app.models import Patient, Dossier, Venue, Mouvement


class PatientAdmin(ModelView, model=Patient):
    name = "Patient"
    name_plural = "Patients"
    icon = "fa-solid fa-user"
    column_list = ["id", "family", "given", "birth_date", "gender", "city"]
    column_searchable_list = ["family", "given", "city"]
    column_sortable_list = ["id", "family", "given", "birth_date"]
    column_default_sort = ("id", True)


class DossierAdmin(ModelView, model=Dossier):
    name = "Dossier"
    name_plural = "Dossiers"
    icon = "fa-solid fa-folder"
    column_list = ["id", "dossier_seq", "patient_id", "dossier_type", "admit_time", "discharge_time"]
    column_searchable_list = ["dossier_seq"]
    column_sortable_list = ["id", "dossier_seq", "admit_time"]
    column_default_sort = ("id", True)
    column_labels = {"patient_id": "Patient"}


class VenueAdmin(ModelView, model=Venue):
    name = "Venue"
    name_plural = "Venues"
    icon = "fa-solid fa-bed"
    column_list = ["id", "venue_seq", "dossier_id", "start_time", "end_time", "uf_hebergement"]
    column_searchable_list = ["venue_seq", "uf_hebergement"]
    column_sortable_list = ["id", "venue_seq", "start_time"]
    column_default_sort = ("id", True)
    column_labels = {"dossier_id": "Dossier"}


class MouvementAdmin(ModelView, model=Mouvement):
    name = "Mouvement"
    name_plural = "Mouvements"
    icon = "fa-solid fa-arrows-alt"
    column_list = ["id", "venue_id", "trigger_event", "when", "uf_responsabilite", "lit"]
    column_searchable_list = ["trigger_event", "uf_responsabilite", "lit"]
    column_sortable_list = ["id", "when", "trigger_event"]
    column_default_sort = ("id", True)
    column_labels = {"venue_id": "Venue"}
