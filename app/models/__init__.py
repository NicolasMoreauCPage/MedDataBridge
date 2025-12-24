"""
Re-export common model classes so callers can `from app.models import Patient, Dossier, ...`.

This keeps backwards compatibility with many scripts and tests that expect
`app.models` to provide these symbols.
"""
from app.models import (
    SQLModel,
    Sequence,
    Patient,
    Dossier,
    Venue,
    Mouvement,
    NGAPAct,
    UCDAct,
    LPPAct,
    CCAMAct,
)

from app.models_identifiers import Identifier, IdentifierType

__all__ = [
    "SQLModel",
    "Sequence",
    "Patient",
    "Dossier",
    "Venue",
    "Mouvement",
    "NGAPAct",
    "UCDAct",
    "LPPAct",
    "CCAMAct",
    "Identifier",
    "IdentifierType",
]
