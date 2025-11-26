from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.utils.flash import flash
from app.models_structure import EntiteJuridique, EntiteGeographique, LocationStatus, LocationMode, LocationPhysicalType
from .helpers import get_context_or_404, get_ej_or_404, get_entite_geo_or_404, templates, resolve_physical_type

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
        request, "ght/eg_form.html",
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
            request, "ght/eg_form.html",
            {"context": context, "entite": entite, "geo": None, "form_data": await request.form()},
            status_code=400,
        )
    
    # Uniqueness checks
    if session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == identifier)).first():
        flash(request, "Un site géographique avec cet identifiant existe déjà.", "error")
        return templates.TemplateResponse(
            request, "ght/eg_form.html",
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
    
    return templates.TemplateResponse(
        request, "ght/eg_detail.html",
        {"context": context, "entite": entite, "geo": geo}
    )