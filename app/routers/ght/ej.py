from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, func

from app.db import get_session
from app.utils.flash import flash
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique, IdentifierNamespace
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from .helpers import get_context_or_404, get_ej_or_404, templates

router = APIRouter()

@router.get("/{context_id}/ej/new")
async def new_entite_juridique_form(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    request.state.ght_context = context
    request.session["ght_context_id"] = context.id
    return templates.TemplateResponse(
        request,
        "ej_form.html",
        {"context": context, "entite": None},
    )

@router.post("/{context_id}/ej/new")
async def create_entite_juridique(
    request: Request,
    context_id: int,
    name: str = Form(...),
    finess_ej: str = Form(...),
    short_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    siren: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    address_line: Optional[str] = Form(None),
    postal_code: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    country: Optional[str] = Form("FR"),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    existing = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == finess_ej)).first()
    if existing:
        flash(request, "Une entité juridique avec ce FINESS existe déjà.", "error")
        return templates.TemplateResponse(
            request, "ej_form.html",
            {"context": context, "entite": None, "form_data": await request.form()},
            status_code=400,
        )

    entite = EntiteJuridique(
        name=name, finess_ej=finess_ej, short_name=short_name, description=description,
        siren=siren, siret=siret, address_line=address_line, postal_code=postal_code,
        city=city, country=country or "FR",
        is_active=str(is_active).lower() in ("1", "true", "yes", "on"),
        ght_context_id=context.id,
    )
    session.add(entite)
    session.commit()
    flash(request, f'Entité juridique "{entite.name}" créée avec succès.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}", status_code=303)

@router.get("/{context_id}/ej/{ej_id}")
async def view_entite_juridique(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    request.session["ght_context_id"] = context_id
    request.session["ej_context_id"] = ej_id
    request.state.ght_context = context
    request.state.ej_context = entite

    geo_ids = [geo.id for geo in entite.entites_geographiques]
    pole_ids = list(session.exec(select(Pole.id).where(Pole.entite_geo_id.in_(geo_ids)))) if geo_ids else []
    service_ids = list(session.exec(select(Service.id).where(Service.pole_id.in_(pole_ids)))) if pole_ids else []
    uf_ids = list(session.exec(select(UniteFonctionnelle.id).where(UniteFonctionnelle.service_id.in_(service_ids)))) if service_ids else []
    uh_ids = list(session.exec(select(UniteHebergement.id).where(UniteHebergement.unite_fonctionnelle_id.in_(uf_ids)))) if uf_ids else []
    chambre_ids = list(session.exec(select(Chambre.id).where(Chambre.unite_hebergement_id.in_(uh_ids)))) if uh_ids else []
    lit_count = session.exec(select(func.count(Lit.id)).where(Lit.chambre_id.in_(chambre_ids))).one() if chambre_ids else 0

    counts = {
        "entites_geo": len(geo_ids),
        "entites_geo_actives": sum(1 for geo in entite.entites_geographiques if getattr(geo, "is_active", True)),
        "poles": len(pole_ids), "services": len(service_ids), "ufs": len(uf_ids),
        "uhs": len(uh_ids), "chambres": len(chambre_ids), "lits": lit_count,
    }
    namespaces = session.exec(select(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == ej_id).order_by(IdentifierNamespace.type, IdentifierNamespace.name)).all()

    return templates.TemplateResponse(
        request, "ej_detail.html",
        {"context": context, "entite": entite, "entites_geographiques": entite.entites_geographiques, "namespaces": namespaces, "counts": counts},
    )

@router.get("/{context_id}/ej/{ej_id}/edit")
async def edit_entite_juridique_form(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    return templates.TemplateResponse(
        request, "ej_form.html",
        {"context": context, "entite": entite},
    )

@router.post("/{context_id}/ej/{ej_id}/edit")
async def update_entite_juridique(
    request: Request,
    context_id: int,
    ej_id: int,
    name: str = Form(...),
    finess_ej: str = Form(...),
    short_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    siren: Optional[str] = Form(None),
    siret: Optional[str] = Form(None),
    address_line: Optional[str] = Form(None),
    postal_code: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    country: Optional[str] = Form("FR"),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)

    if finess_ej != entite.finess_ej:
        exists = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == finess_ej).where(EntiteJuridique.id != entite.id)).first()
        if exists:
            flash(request, "Une entité juridique avec ce FINESS existe déjà.", "error")
            return templates.TemplateResponse(
                request, "ej_form.html",
                {"context": context, "entite": entite, "form_data": await request.form()},
                status_code=400,
            )

    entite.name, entite.finess_ej, entite.short_name, entite.description = name, finess_ej, short_name, description
    entite.siren, entite.siret = siren, siret
    entite.address_line, entite.postal_code, entite.city, entite.country = address_line, postal_code, city, country or "FR"
    entite.is_active = str(is_active).lower() in ("1", "true", "yes", "on")
    
    session.add(entite)
    session.commit()
    flash(request, f'Entité juridique "{entite.name}" mise à jour.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}/ej/{entite.id}", status_code=303)