"""Schémas Pydantic organisés par domaine."""

from app.schemas.legacy import (
    DossierBase,
    DossierCreate,
    DossierResponse,
    DossierUpdate,
    MouvementBase,
    MouvementCreate,
    MouvementResponse,
    PatientBase,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    VenueBase,
    VenueCreate,
    VenueResponse,
)
from app.schemas.lpp import LPPActBase, LPPActCreate, LPPActResponse, LPPActUpdate
from app.schemas.ucd import UCDActBase, UCDActCreate, UCDActResponse, UCDActUpdate

__all__ = [
    "PatientBase",
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "DossierBase",
    "DossierCreate",
    "DossierUpdate",
    "DossierResponse",
    "VenueBase",
    "VenueCreate",
    "VenueResponse",
    "MouvementBase",
    "MouvementCreate",
    "MouvementResponse",
    "UCDActBase",
    "UCDActCreate",
    "UCDActUpdate",
    "UCDActResponse",
    "LPPActBase",
    "LPPActCreate",
    "LPPActUpdate",
    "LPPActResponse",
]
