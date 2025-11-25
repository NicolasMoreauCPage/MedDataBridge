from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.db import get_session
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
import logging

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["ght"])

# ...existing code for structure routes (poles, services, etc.)...
# Example stub:
@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}/structure")
async def view_structure(
    request: Request,
    context_id: int,
    ej_id: int,
    eg_id: int,
    session: Session = Depends(get_session),
):
    logging.error(f"DEBUG: Accessing Structure route with context_id={context_id}, ej_id={ej_id}, eg_id={eg_id}")
    # ...existing code for structure rendering...
    return templates.TemplateResponse(
        request,
        "structure_detail.html",
        {
            "context": context_id,
            "ej_id": ej_id,
            "eg_id": eg_id,
        },
    )
