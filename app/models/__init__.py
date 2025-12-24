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
    """app.models package placeholder.

    This file exists so `import app.models` resolves as a package. The real
    models are defined in app/models.py module; avoid re-exporting here to
    prevent import cycles during test collection.
    """

    __all__ = []
    "Patient",
