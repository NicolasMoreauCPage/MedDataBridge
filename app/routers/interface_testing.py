"""
Module de test d'interfaces (stub).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/interface-testing", tags=["Interface Testing"])
ui_router = APIRouter(prefix="/ui/interface-testing", tags=["Interface Testing UI"])

# TODO: Implémenter les fonctionnalités de test d'interfaces GAM/GAP
