"""
GHT administration router module.

This module provides routes for managing GHT contexts, their associated entities
(EntiteJuridique, EntiteGeographique), and the hospital structure hierarchy
(Pole, Service, UF, etc.).

The logic is split into sub-routers for better organization.
"""
from fastapi import APIRouter

from . import context, ej, eg, namespaces, structure
from .. import namespaces as main_namespaces

router = APIRouter()

# Include all the sub-routers
router.include_router(context.router)
router.include_router(namespaces.router)
router.include_router(main_namespaces.router)
router.include_router(ej.router)
router.include_router(eg.router)
router.include_router(structure.router)

__all__ = ["router"]
