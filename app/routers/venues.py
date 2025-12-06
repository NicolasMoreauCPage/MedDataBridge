from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import select
from datetime import datetime
from app.db import get_session, peek_next_sequence
from app.models import Venue, Dossier, Patient
from app.dependencies.ght import require_ght_context
from app.services import venues_service
from app.services.venues_service import VenueCreateSchema
from app.utils.flash import flash


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(
    prefix="/venues",
    tags=["venues"],
    dependencies=[Depends(require_ght_context)],
)

@router.get("", response_class=HTMLResponse)
def list_venues(
    request: Request,
    dossier_id: int | None = Query(None, description="Filter by dossier id"),
    patient_id: int | None = Query(None, description="Filter by patient id"),
    session=Depends(get_session)
):
    """Displays the list of venues, optional filters by dossier or patient.

    The router has a GHT context dependency so the results will be scoped
    to the current EJ/GHT if available.
    """
    ght_context = getattr(request.state, "ght_context", None)
    ej_context = getattr(request.state, "ej_context", None)

    query = select(Venue)
    # Filter by dossier or patient if provided
    if dossier_id:
        query = query.where(Venue.dossier_id == dossier_id)
    elif patient_id:
        # Join through Dossier to filter by patient
        query = query.join(Dossier, Venue.dossier_id == Dossier.id).where(Dossier.patient_id == patient_id)
    else:
        if ej_context and getattr(ej_context, "id", None):
            query = query.where(Venue.entite_juridique_id == ej_context.id)
        elif ght_context and getattr(ght_context, "id", None):
            # If a GHT context exists, try to limit to that ght id when available
            # Venues may not have direct ght field; rely on EJ when possible.
            pass

    venues = session.exec(query).all()

    rows = [
        {
            "cells": [v.id, v.venue_seq, v.code or v.label or "", v.assigned_location or "", v.start_time],
            "detail_url": f"/venues/{v.id}",
            "edit_url": f"/venues/{v.id}/edit",
            "delete_url": f"/venues/{v.id}/delete",
        }
        for v in venues
    ]

    breadcrumbs = [{"label": "Venues", "url": "/venues"}]
    ctx = {
        "request": request,
        "title": "Venues",
        "breadcrumbs": breadcrumbs,
        "headers": ["ID", "Seq", "Code / Label", "Assigned", "Début"],
        "rows": rows,
        "new_url": "/venues/new",
        "filters": [],
        "actions": [],
        "show_actions": True,
    }

    templates = get_templates_with_filters(request)
    return templates.TemplateResponse(request, "list.html", ctx)


@router.get("/new", response_class=HTMLResponse)
def new_venue(
    request: Request, 
    dossier_id: int | None = Query(None, description="ID du dossier parent (pré-rempli si fourni)"),
    session=Depends(get_session)
):
    next_seq = peek_next_sequence(session, "venue")
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    
    prefill_dossier_id = dossier_id
    if prefill_dossier_id is None and hasattr(request.state, 'dossier_context') and request.state.dossier_context:
        prefill_dossier_id = request.state.dossier_context.id
    
    if prefill_dossier_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Impossible de créer une venue : aucun dossier n'est spécifié.")
    
    uf_options = []
    dossier = session.get(Dossier, prefill_dossier_id)
    if dossier and dossier.entite_juridique_id:
        from app.models_structure import EntiteJuridique, UniteFonctionnelle, Service, Pole, EntiteGeographique
        ufs = session.exec(
            select(UniteFonctionnelle)
            .join(Service, UniteFonctionnelle.service_id == Service.id)
            .join(Pole, Service.pole_id == Pole.id)
            .join(EntiteGeographique, Pole.entite_geo_id == EntiteGeographique.id)
            .where(EntiteGeographique.entite_juridique_id == dossier.entite_juridique_id)
            .where(UniteFonctionnelle.status == "active")
        ).all()
        uf_options = [{"value": uf.identifier, "label": f"{uf.identifier} - {uf.name}"} for uf in ufs]
    
    dossier_seq_value = dossier.dossier_seq if dossier else ''
    fields = [
        {"label": "Numéro de dossier", "name": "dossier_seq", "type": "number", "required": True, "value": dossier_seq_value, "readonly": True},
        {"name": "dossier_id", "type": "hidden", "value": prefill_dossier_id or ''},
        {"label": "UF de responsabilité", "name": "uf_responsabilite", "type": "select", "required": True, "options": uf_options or [{"value": "", "label": "Aucune UF disponible"}], "empty_message": "Aucune UF disponible pour le dossier sélectionné. Vérifiez que l'EJ associée contient des structures organisationnelles (Service > UF)."},
        {"label": "Début de venue", "name": "start_time", "type": "datetime-local", "value": now_str, "required": True},
        {"label": "Numéro de venue", "name": "venue_seq", "type": "number", "value": next_seq, "readonly": True},
    ]
    return get_templates_with_filters(request).TemplateResponse(request, "form.html", {"request": request, "title": "Nouvelle venue", "fields": fields})


@router.post("/new")
def create_venue(
    request: Request,
    dossier_id: int = Form(...),
    uf_responsabilite: str = Form(...),
    start_time: str = Form(...),
    venue_seq: int | None = Form(None),
    hospital_service: str = Form(None),
    assigned_location: str = Form(None),
    attending_provider: str = Form(None),
    code: str = Form(None),
    label: str = Form(None),
    session=Depends(get_session)
):
    try:
        start_dt = datetime.fromisoformat(start_time)
        venue_data = VenueCreateSchema(
            dossier_id=dossier_id,
            uf_responsabilite=uf_responsabilite,
            start_time=start_dt,
            venue_seq=venue_seq,
            hospital_service=hospital_service,
            assigned_location=assigned_location,
            attending_provider=attending_provider,
            code=code,
            label=label,
        )
        venues_service.create_venue(session=session, venue_data=venue_data)
        flash(request, "Venue créée avec succès.", "success")
        return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)
    except Exception as e:
        flash(request, f"Erreur lors de la création de la venue: {e}", "error")
        return RedirectResponse(url=f"/venues/new?dossier_id={dossier_id}", status_code=303)

# Other endpoints (GET /id, GET /id/edit, POST /id/edit, POST /id/delete) remain unchanged for now
@router.get("/{venue_id}", response_class=HTMLResponse)
def venue_detail(venue_id: int, request: Request, session=Depends(get_session)):
    v = session.get(Venue, venue_id)
    if not v:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    # Charger le dossier et le patient pour le contexte
    dossier = session.get(Dossier, v.dossier_id) if v.dossier_id else None
    patient = session.get(type(dossier.patient), dossier.patient_id) if dossier and dossier.patient_id else None
    return get_templates_with_filters(request).TemplateResponse(request, "venue_detail.html", {
        "request": request,
        "venue": v,
        "dossier": dossier,
        "patient": patient
    })


@router.get("/{venue_id}/edit", response_class=HTMLResponse)
def edit_venue(venue_id: int, request: Request, session=Depends(get_session)):
    v = session.get(Venue, venue_id)
    if not v:
            return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    
    # Récupérer la liste des UF disponibles pour l'EJ du dossier
    uf_options = []
    if v.dossier_id:
        dossier = session.get(Dossier, v.dossier_id)
        if dossier and dossier.entite_juridique_id:
            from app.models_structure import EntiteJuridique
            ej = session.get(EntiteJuridique, dossier.entite_juridique_id)
            if ej:
                # Récupérer toutes les UF de la structure
                from app.models_structure import UniteFonctionnelle, Service, Pole, EntiteGeographique
                ufs = session.exec(
                    select(UniteFonctionnelle)
                    .join(Service, UniteFonctionnelle.service_id == Service.id)
                    .join(Pole, Service.pole_id == Pole.id)
                    .join(EntiteGeographique, Pole.entite_geo_id == EntiteGeographique.id)
                    .where(EntiteGeographique.entite_juridique_id == ej.id)
                ).all()
                uf_options = [
                    {"value": uf.identifier, "label": f"{uf.identifier} - {uf.name}"} for uf in ufs
                ]
    
    fields = [
        {"label": "Dossier ID", "name": "dossier_id", "type": "number", "value": v.dossier_id, "required": True},
        {"label": "UF de responsabilité", "name": "uf_responsabilite", "type": "select", "value": v.uf_responsabilite or '', "required": True, "options": uf_options, "empty_message": "Aucune UF disponible. Vérifiez que l'EJ du dossier contient des structures organisationnelles."},
        {"label": "Début de venue", "name": "start_time", "type": "datetime-local", "value": v.start_time.strftime('%Y-%m-%dT%H:%M') if v.start_time else '', "required": True},
        {"label": "Numéro de séquence", "name": "venue_seq", "type": "number", "value": v.venue_seq or 0},
    ]
    return get_templates_with_filters(request).TemplateResponse(request, "form.html", {"request": request, "title": "Modifier venue", "fields": fields, "action_url": f"/venues/{venue_id}/edit"})


@router.post("/{venue_id}/edit")
def update_venue(
    venue_id: int,
    dossier_id: int = Form(...),
    uf_responsabilite: str = Form(...),
    start_time: str = Form(...),
    venue_seq: int = Form(...),
    session=Depends(get_session),
    request: Request = None
):
    v = session.get(Venue, venue_id)
    if not v:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    v.dossier_id = dossier_id
    v.uf_responsabilite = uf_responsabilite
    v.start_time = datetime.fromisoformat(start_time)
    v.venue_seq = venue_seq
    session.add(v); session.commit()
    
    # Refresh with relationships for emit_to_senders
    session.refresh(v, ["dossier"])
    if v.dossier:
        session.refresh(v.dossier, ["patient"])
    
    from app.services.emit_on_create import emit_to_senders
    emit_to_senders(v, "venue", session)
    return RedirectResponse(url="/venues", status_code=303)


@router.post("/{venue_id}/delete")
def delete_venue(venue_id: int, request: Request, session=Depends(get_session)):
    v = session.get(Venue, venue_id)
    if not v:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    dossier_id = v.dossier_id
    # Refresh relationships so emit_to_senders can access them before deletion
    session.refresh(v)
    if v.dossier:
        session.refresh(v.dossier, ["patient"])

    from app.services.emit_on_create import emit_to_senders
    # Emit before deleting to avoid DetachedInstanceError in emit pipeline
    emit_to_senders(v, "venue", session, operation="delete")
    session.delete(v); session.commit()
    return RedirectResponse(url=f"/venues?dossier_id={dossier_id}", status_code=303)
