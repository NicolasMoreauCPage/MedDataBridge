"""Compatibilité : rendez-vous déplacés vers ``app.models.appointments``."""

from app.models.appointments import Appointment

__all__ = ["Appointment"]
