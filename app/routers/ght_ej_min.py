"""Minimal EJ detail router to guarantee availability of /admin/ght/{context_id}/ej/{ej_id}.

This is a durable lightweight replacement for the previous fallback router.
It does not duplicate the whole admin logic; it only renders the EJ detail
template with basic counters so that admin navigation and tests relying on
that page remain stable even if the large `ght.py` router partially loads.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.models_structure_fhir import GHTContext, EntiteJuridique, IdentifierNamespace
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit

router = APIRouter(prefix="/ght", tags=["ght-ej-min"])
templates = Jinja2Templates(directory="app/templates")


def _ctx(session: Session, ctx_id: int) -> GHTContext:
    ctx = session.get(GHTContext, ctx_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    return ctx


def _ej(session: Session, context: GHTContext, ej_id: int) -> EntiteJuridique:
    ej = session.exec(
        select(EntiteJuridique)
        .where(EntiteJuridique.id == ej_id)
        .where(EntiteJuridique.ght_context_id == context.id)
    ).first()
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    return ej


@router.get("/{context_id}/ej/{ej_id}")
async def ej_detail(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = _ctx(session, context_id)
    entite = _ej(session, context, ej_id)

    geo_ids = [g.id for g in entite.entites_geographiques]
    pole_ids = service_ids = uf_ids = uh_ids = chambre_ids = []
    if geo_ids:
        pole_ids = list(session.exec(select(Pole.id).where(Pole.entite_geo_id.in_(geo_ids))))
    if pole_ids:
        service_ids = list(session.exec(select(Service.id).where(Service.pole_id.in_(pole_ids))))
    if service_ids:
        uf_ids = list(session.exec(select(UniteFonctionnelle.id).where(UniteFonctionnelle.service_id.in_(service_ids))))
    if uf_ids:
        uh_ids = list(session.exec(select(UniteHebergement.id).where(UniteHebergement.unite_fonctionnelle_id.in_(uf_ids))))
    if uh_ids:
        chambre_ids = list(session.exec(select(Chambre.id).where(Chambre.unite_hebergement_id.in_(uh_ids))))
    lit_count = 0
    if chambre_ids:
        lit_count = session.exec(select(func.count(Lit.id)).where(Lit.chambre_id.in_(chambre_ids))).one()

    counts = {
        "entites_geo": len(geo_ids),
        "poles": len(pole_ids),
        "services": len(service_ids),
        "ufs": len(uf_ids),
        "uhs": len(uh_ids),
        "chambres": len(chambre_ids),
        "lits": lit_count,
    }

    namespaces = session.exec(
        select(IdentifierNamespace)
        .where(IdentifierNamespace.entite_juridique_id == ej_id)
        .order_by(IdentifierNamespace.type, IdentifierNamespace.name)
    ).all()

    return templates.TemplateResponse(
        request,
        "ej_detail.html",
        {
            "context": context,
            "entite": entite,
            "entites_geographiques": entite.entites_geographiques,
            "namespaces": namespaces,
            "counts": counts,
        },
    )
