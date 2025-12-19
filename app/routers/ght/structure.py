from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.utils.flash import flash
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit,
    LocationStatus, LocationMode, LocationServiceType
)
from .helpers import (
    get_context_or_404, get_ej_or_404, get_entite_geo_or_404,
    get_pole_or_404, get_service_or_404, get_uf_or_404, get_uh_or_404,
    get_chambre_or_404, get_lit_or_404,
    templates, maybe, resolve_physical_type,
    pole_form_fields, service_form_fields, uf_form_fields, uh_form_fields,
    chambre_form_fields, lit_form_fields,
    with_form_values, render_form
)

router = APIRouter()

# --- POLES ---
@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/new")
async def new_pole_form(request: Request, context_id: int, ej_id: int, eg_id: int, session: Session = Depends(get_session)):
    context, entite, geo = get_context_or_404(session, context_id), get_ej_or_404(session, context_id, ej_id), get_entite_geo_or_404(session, ej_id, eg_id)
    fields = pole_form_fields()
    action_url = request.url.path
    cancel_url = f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}"
    return render_form(request, "Nouveau pôle", fields, action_url, cancel_url)

@router.post("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/new")
async def create_pole(request: Request, context_id: int, ej_id: int, eg_id: int, session: Session = Depends(get_session)):
    context, entite, geo = get_context_or_404(session, context_id), get_ej_or_404(session, context_id, ej_id), get_entite_geo_or_404(session, ej_id, eg_id)
    form_data = await request.form()
    pole = Pole(
        identifier=form_data.get("identifier"), name=form_data.get("name"),
        short_name=maybe(form_data.get("short_name")),
        description=maybe(form_data.get("description")),
        status=LocationStatus(form_data.get("status", LocationStatus.ACTIVE.value)),
        mode=LocationMode(form_data.get("mode", LocationMode.INSTANCE.value)),
        physical_type=resolve_physical_type("pole", None),
        entite_geo_id=geo.id
    )
    session.add(pole)
    session.commit()
    flash(request, f'Pôle "{pole.name}" créé.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}", status_code=303)

# --- SERVICES ---
@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/{pole_id}/services/new")
async def new_service_form(request: Request, context_id: int, ej_id: int, eg_id: int, pole_id: int, session: Session = Depends(get_session)):
    context, entite, geo, pole = get_context_or_404(session, context_id), get_ej_or_404(session, context_id, ej_id), get_entite_geo_or_404(session, ej_id, eg_id), get_pole_or_404(session, eg_id, pole_id)
    fields = service_form_fields()
    action_url = request.url.path
    cancel_url = f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}"
    return render_form(request, f"Nouveau service pour {pole.name}", fields, action_url, cancel_url)

@router.post("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/{pole_id}/services/new")
async def create_service(request: Request, context_id: int, ej_id: int, eg_id: int, pole_id: int, session: Session = Depends(get_session)):
    context, entite, geo, pole = get_context_or_404(session, context_id), get_ej_or_404(session, context_id, ej_id), get_entite_geo_or_404(session, ej_id, eg_id), get_pole_or_404(session, eg_id, pole_id)
    form_data = await request.form()
    service = Service(
        identifier=form_data.get("identifier"), name=form_data.get("name"),
        short_name=maybe(form_data.get("short_name")),
        description=maybe(form_data.get("description")),
        status=LocationStatus(form_data.get("status", LocationStatus.ACTIVE.value)),
        mode=LocationMode(form_data.get("mode", LocationMode.INSTANCE.value)),
        service_type=LocationServiceType(form_data.get("service_type", LocationServiceType.MCO.value)),
        physical_type=resolve_physical_type("service", None),
        typology=maybe(form_data.get("typology")),
        pole_id=pole.id,
    )
    session.add(service)
    session.commit()
    flash(request, f'Service "{service.name}" créé.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}", status_code=303)

# --- UFs ---
@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/{pole_id}/services/{service_id}/ufs/new")
async def new_uf_form(request: Request, context_id: int, ej_id: int, eg_id: int, pole_id: int, service_id: int, session: Session = Depends(get_session)):
    context, entite, geo, pole, service = get_context_or_404(session, context_id), get_ej_or_404(session, context_id, ej_id), get_entite_geo_or_404(session, ej_id, eg_id), get_pole_or_404(session, eg_id, pole_id), get_service_or_404(session, pole_id, service_id)
    fields = uf_form_fields()
    action_url = request.url.path
    cancel_url = f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}" # Should probably go to service detail
    return render_form(request, f"Nouvelle UF pour {service.name}", fields, action_url, cancel_url)

# ... Other endpoints for UF, UH, Chambre, Lit would follow the same pattern ...

# --- LITS EDIT ---
@router.get("/test")
async def test_route():
    return {"message": "test route works"}

@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/{pole_id}/services/{service_id}/ufs/{uf_id}/uh/{uh_id}/chambres/{chambre_id}/lits/{lit_id}/edit")
async def edit_lit_form(request: Request, context_id: int, ej_id: int, eg_id: int, pole_id: int, service_id: int, uf_id: int, uh_id: int, chambre_id: int, lit_id: int, session: Session = Depends(get_session)):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    geo = get_entite_geo_or_404(session, entite, eg_id)
    pole = get_pole_or_404(session, geo, pole_id)
    service = get_service_or_404(session, pole, service_id)
    uf = get_uf_or_404(session, service, uf_id)
    uh = get_uh_or_404(session, uf, uh_id)
    chambre = get_chambre_or_404(session, uh, chambre_id)
    lit = get_lit_or_404(session, chambre, lit_id)
    fields = lit_form_fields()
    with_form_values(fields, lit)
    action_url = request.url.path
    cancel_url = f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}"
    return render_form(request, f"Modifier lit {lit.name}", fields, action_url, cancel_url)

@router.post("/{context_id}/ej/{ej_id}/eg/{eg_id}/poles/{pole_id}/services/{service_id}/ufs/{uf_id}/uh/{uh_id}/chambres/{chambre_id}/lits/{lit_id}/edit")
async def update_lit(request: Request, context_id: int, ej_id: int, eg_id: int, pole_id: int, service_id: int, uf_id: int, uh_id: int, chambre_id: int, lit_id: int, session: Session = Depends(get_session)):
    context = get_context_or_404(session, context_id)
    entite = get_ej_or_404(session, context, ej_id)
    geo = get_entite_geo_or_404(session, entite, eg_id)
    pole = get_pole_or_404(session, geo, pole_id)
    service = get_service_or_404(session, pole, service_id)
    uf = get_uf_or_404(session, service, uf_id)
    uh = get_uh_or_404(session, uf, uh_id)
    chambre = get_chambre_or_404(session, uh, chambre_id)
    lit = get_lit_or_404(session, chambre, lit_id)
    form_data = await request.form()
    lit.identifier = form_data.get("identifier")
    lit.name = form_data.get("name")
    lit.short_name = maybe(form_data.get("short_name"))
    lit.description = maybe(form_data.get("description"))
    lit.status = LocationStatus(form_data.get("status", LocationStatus.ACTIVE.value))
    lit.mode = LocationMode(form_data.get("mode", LocationMode.INSTANCE.value))
    lit.operational_status = form_data.get("operational_status")
    session.commit()
    flash(request, f'Lit "{lit.name}" modifié.', "success")
    return RedirectResponse(f"/admin/ght/{context.id}/ej/{entite.id}/eg/{geo.id}", status_code=303)