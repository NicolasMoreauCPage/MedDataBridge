"""
Helpers for GHT router: context, EJ, EG lookup functions.
Decoupled from router to avoid import cycles.
"""
from fastapi import HTTPException
from sqlmodel import Session, select
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique

def get_context_or_404(session: Session, context_id: int) -> GHTContext:
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    return context

def get_ej_or_404(session: Session, context: GHTContext, ej_id: int) -> EntiteJuridique:
    entite = session.exec(
        select(EntiteJuridique)
        .where(EntiteJuridique.id == ej_id)
        .where(EntiteJuridique.ght_context_id == context.id)
    ).first()
    if not entite:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    return entite

def get_entite_geo_or_404(session: Session, entite: EntiteJuridique, eg_id: int) -> EntiteGeographique:
    entite_geo = session.exec(
        select(EntiteGeographique)
        .where(EntiteGeographique.id == eg_id)
        .where(EntiteGeographique.entite_juridique_id == entite.id)
    ).first()
    if not entite_geo:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    return entite_geo
