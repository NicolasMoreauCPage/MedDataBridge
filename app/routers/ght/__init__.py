"""
GHT administration router module (partially refactored).

This module provides routes for managing GHT contexts, their associated entities,
and hospital structure hierarchy.

Current structure:
- context.py: GHT context CRUD operations (~270 lines)
- helpers.py: Form builders and entity getters (~600 lines)
- [To be refactored]: entities.py, structure.py

Total reduction: ~870 lines extracted from monolithic 3463-line file.
"""

# For now, simply re-export the context router which contains GHT context CRUD
# The router already has appropriate tags and will be mounted at /ght by app.py
"""Routes pour le module GHT."""
from fastapi import APIRouter
from .context import router as context_router
from .namespaces import router as namespaces_router

router = APIRouter()
router.include_router(context_router)
router.include_router(namespaces_router)

# Note: Original ght.py still contains EJ/EG and structure routes (lines 897-3464)
# These will be refactored in future iterations to:
# - entities.py: EntiteJuridique & EntiteGeographique CRUD
# - structure.py: Pole/Service/UF/UH/Chambre/Lit CRUD

__all__ = ["router"]
