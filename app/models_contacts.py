"""Compatibilité historique des modèles de contacts HL7.

Les modèles sont désormais regroupés dans :mod:`app.models.contacts`.
"""

from app.models.contacts import (
    AdministrativeSex,
    ContactRelationship,
    ContactRole,
    PatientContact,
    VenueContact,
)

__all__ = [
    "AdministrativeSex",
    "ContactRelationship",
    "ContactRole",
    "PatientContact",
    "VenueContact",
]
