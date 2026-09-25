"""Compatibilité : praticiens déplacés vers ``app.models.practitioners``."""

from app.models.practitioners import MedecinResponsable

__all__ = ["MedecinResponsable"]
