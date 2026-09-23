"""Chargement du contexte ORM nécessaire aux messages PAM de mouvement."""

from sqlmodel import Session, select

from app.models import Dossier, Patient, Venue


def load_movement_context(session: Session, mouvement):
    """Retourne ``(venue, dossier, patient)`` sans déclencher de lazy-load tardif."""
    venue = getattr(mouvement, "venue", None)
    if not venue and getattr(mouvement, "venue_id", None):
        venue = session.exec(select(Venue).where(Venue.id == mouvement.venue_id)).first()

    dossier = getattr(venue, "dossier", None) if venue else None
    if venue and not dossier and getattr(venue, "dossier_id", None):
        dossier = session.exec(select(Dossier).where(Dossier.id == venue.dossier_id)).first()

    patient = getattr(dossier, "patient", None) if dossier else None
    if dossier and not patient and getattr(dossier, "patient_id", None):
        patient = session.exec(select(Patient).where(Patient.id == dossier.patient_id)).first()
    return venue, dossier, patient
