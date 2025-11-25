from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.db import get_session
from app.models_structure import GHTContext, EntiteJuridique
import logging

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["ght"])

def _get_context_or_404(session: Session, context_id: int) -> GHTContext:
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    return context

def _get_ej_or_404(session: Session, context: GHTContext, ej_id: int) -> EntiteJuridique:
    entite = session.exec(
        select(EntiteJuridique)
        .where(EntiteJuridique.id == ej_id)
        .where(EntiteJuridique.ght_context_id == context.id)
    ).first()
    if not entite:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    return entite

@router.get("/{context_id}/ej/{ej_id}")
async def view_entite_juridique(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    logging.error(f"DEBUG: Accessing EJ route with context_id={context_id}, ej_id={ej_id}")
    context = _get_context_or_404(session, context_id)
    logging.error(f"DEBUG: Got context {context.name}")
    entite = _get_ej_or_404(session, context, ej_id)
    logging.error(f"DEBUG: Got entite {entite.name}")
    request.session["ght_context_id"] = context_id
    request.session["ej_context_id"] = ej_id
    # ...existing code for EJ detail rendering...
    return templates.TemplateResponse(
        request,
        "ej_detail.html",
        {
            "context": context,
            "entite": entite,
        },
    )
