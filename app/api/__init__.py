"""
Package API pour les endpoints REST structurés.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["API"])

# Les sous-modules sont importés ici si nécessaire
