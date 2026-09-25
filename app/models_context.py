"""Compatibilité : mappings de contexte déplacés vers ``app.models``."""

from app.models.context import (
    DossierContextMapping,
    EndpointContext,
    MouvementContextMapping,
    PatientContextMapping,
    VenueContextMapping,
)

__all__ = [
    "DossierContextMapping",
    "EndpointContext",
    "MouvementContextMapping",
    "PatientContextMapping",
    "VenueContextMapping",
]
