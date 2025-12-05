from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, func

from app.db import get_session
from app.utils.flash import flash
from app.models_structure import EntiteJuridique, EntiteGeographique, LocationStatus, LocationMode, LocationPhysicalType
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from .helpers import get_context_or_404, get_ej_or_404, get_entite_geo_or_404, templates, resolve_physical_type
from app.services.structure_tree import build_structure_tree_for_template

router = APIRouter()

@router.get("/{context_id}/ej/{ej_id}/eg/new")
async def new_entite_geographique_form(
    request: Request,
    context_id: int,
    ej_id: int,
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    return templates.TemplateResponse(
        request, "eg_form.html",
        {"context": context, "entite": entite, "geo": None},
    )

@router.post("/{context_id}/ej/{ej_id}/eg/new")
async def create_entite_geographique(
    request: Request,
    context_id: int,
    ej_id: int,
    name: str = Form(...),
    identifier: str = Form(...),
    finess: str = Form(...),
    short_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status: str = Form(LocationStatus.ACTIVE.value),
    mode: str = Form(LocationMode.INSTANCE.value),
    physical_type: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)

    # Basic validation
    if not name or not identifier or not finess:
        flash(request, "Nom, Identifiant et FINESS sont obligatoires.", "error")
        return templates.TemplateResponse(
            request, "eg_form.html",
            {"context": context, "entite": entite, "geo": None, "form_data": await request.form()},
            status_code=400,
        )
    
    # Uniqueness checks
    if session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == identifier)).first():
        flash(request, "Un site géographique avec cet identifiant existe déjà.", "error")
        return templates.TemplateResponse(
            request, "eg_form.html",
            {"context": context, "entite": entite, "geo": None, "form_data": await request.form()},
            status_code=400,
        )

    geo = EntiteGeographique(
        name=name, identifier=identifier, finess=finess, short_name=short_name,
        description=description, status=LocationStatus(status), mode=LocationMode(mode),
        physical_type=resolve_physical_type("entite_geographique", physical_type),
        entite_juridique_id=entite.id,
    )
    session.add(geo)
    session.commit()
    session.refresh(geo)

    flash(request, f'Entité géographique "{geo.name}" créée.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}", status_code=303)

@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}")
async def view_entite_geographique(
    request: Request,
    context_id: int,
    ej_id: int,
    eg_id: int,
    session: Session = Depends(get_session)
):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    geo = get_entite_geo_or_404(session, entite, eg_id)
    
    pole_ids = [pole.id for pole in geo.poles]
    service_ids = list(session.exec(select(Service.id).where(Service.pole_id.in_(pole_ids)))) if pole_ids else []
    uf_ids = list(session.exec(select(UniteFonctionnelle.id).where(UniteFonctionnelle.service_id.in_(service_ids)))) if service_ids else []
    uh_ids = list(session.exec(select(UniteHebergement.id).where(UniteHebergement.unite_fonctionnelle_id.in_(uf_ids)))) if uf_ids else []
    chambre_ids = list(session.exec(select(Chambre.id).where(Chambre.unite_hebergement_id.in_(uh_ids)))) if uh_ids else []
    lit_count = session.exec(select(func.count(Lit.id)).where(Lit.chambre_id.in_(chambre_ids))).one() if chambre_ids else 0

    counts = {
        "poles": len(pole_ids),
        "poles_actifs": sum(1 for pole in geo.poles if getattr(pole, "is_active", True)),
        "services": len(service_ids), "ufs": len(uf_ids),
        "uhs": len(uh_ids), "chambres": len(chambre_ids), "lits": lit_count,
    }
    # Reuse the shared tree builder used for template rendering
    structure_tree, lit_operational, lits_actifs = build_structure_tree_for_template(session, geo)
    counts["lits_actifs"] = lits_actifs

    return templates.TemplateResponse(
        request, "eg_detail.html",
        {"context": context, "entite": entite, "geo": geo, "counts": counts,
         "structure_tree": structure_tree, "lit_operational": lit_operational}
    )