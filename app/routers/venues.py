from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from datetime import datetime
from app.db import get_session, get_next_sequence, peek_next_sequence
from app.models import Venue, Dossier, Patient
from app.services.emit_on_create import emit_to_senders
from app.dependencies.ght import require_ght_context

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(
    prefix="/venues",
    tags=["venues"],
    dependencies=[Depends(require_ght_context)],
)

@router.get("", response_class=HTMLResponse)
def list_venues(
    request: Request,
    dossier_id: int | None = Query(None, description="ID du dossier dont on veut voir les venues"),
    patient_id: int | None = Query(None, description="ID du patient pour filtrer les venues par tous ses dossiers"),
    session=Depends(get_session)
):
    venues = []
    dossier = None
    patient = None
    if dossier_id:
        dossier = session.get(Dossier, dossier_id)
        if not dossier:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "request": request,
                    "title": "Dossier introuvable",
                    "message": "Le dossier spécifié n'existe pas. Veuillez sélectionner un dossier valide.",
                    "back_url": "/dossiers"
                },
                status_code=404
            )
        session.refresh(dossier, ['patient'])
        venues = session.exec(select(Venue).where(Venue.dossier_id == dossier_id)).all()
        patient = dossier.patient if hasattr(dossier, 'patient') else None
    elif patient_id:
        patient = session.get(Patient, patient_id)
        if not patient:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "request": request,
                    "title": "Patient introuvable",
                    "message": "Le patient spécifié n'existe pas.",
                    "back_url": "/patients"
                },
                status_code=404
            )
        # Récupérer tous les dossiers du patient et leurs venues
        dossiers = getattr(patient, 'dossiers', [])
        for d in dossiers:
            venues.extend(session.exec(select(Venue).where(Venue.dossier_id == d.id)).all())
    else:
        # Filtrer par contexte EJ si présent
        ej_context = getattr(request.state, "ej_context", None)
        if ej_context and getattr(ej_context, "id", None):
            # Récupérer tous les dossiers de l'EJ
            dossier_ids = [d.id for d in session.exec(select(Dossier).where(Dossier.entite_juridique_id == ej_context.id)).all()]
            if dossier_ids:
                venues = session.exec(select(Venue).where(Venue.dossier_id.in_(dossier_ids))).all()
            else:
                venues = []
        else:
            venues = session.exec(select(Venue)).all()

    rows = [
        {
            "cells": [
                v.venue_seq,
                v.id,
                v.dossier_id,
                v.uf_responsabilite,
                v.start_time.strftime("%d/%m/%Y %H:%M") if v.start_time else None
            ],
            "detail_url": f"/venues/{v.id}",
            "timeline_url": f"/timeline/venue/{v.id}",
            "edit_url": f"/venues/{v.id}/edit",
            "delete_url": f"/venues/{v.id}/delete"
        }
        for v in venues
    ]

    breadcrumbs = [{"label": "Venues", "url": "/venues"}]
    if dossier_id and dossier:
        breadcrumbs.insert(0, {"label": f"Dossier #{dossier.dossier_seq}", "url": f"/dossiers/{dossier_id}"})
        if dossier.patient:
            breadcrumbs.insert(0, {
                "label": f"Patient: {dossier.patient.family} {dossier.patient.given}",
                "url": f"/patients/{dossier.patient.id}"
            })
    elif patient_id and patient:
        breadcrumbs.insert(0, {
            "label": f"Patient: {patient.family} {patient.given}",
            "url": f"/patients/{patient.id}"
        })

    filters = [
        {
            "label": "UF responsabilité",
            "name": "uf",
            "type": "text",
            "placeholder": "Filtrer par UF"
        },
        {
            "label": "Service",
            "name": "service",
            "type": "select",
            "placeholder": "Tous les services",
            "options": [
                {"value": "cardiology", "label": "Cardiologie"},
                {"value": "neurology", "label": "Neurologie"},
                {"value": "oncology", "label": "Oncologie"},
                {"value": "pediatrics", "label": "Pédiatrie"},
                {"value": "other", "label": "Autre"}
            ]
        },
        {
            "label": "Local",
            "name": "location",
            "type": "text",
            "placeholder": "Filtrer par local"
        }
    ]

    # Définir les actions disponibles
    actions = [
        {
            "type": "link",
            "label": "Export FHIR",
            "url": "/venues/export/fhir"
        },
        {
            "type": "link",
            "label": "Export HL7",
            "url": "/venues/export/hl7"
        }
    ]

    # Construire le contexte complet
    ctx = {
        "request": request,
        "title": "Venues" if not dossier_id else f"Venues du dossier #{dossier.dossier_seq}",
        "breadcrumbs": breadcrumbs,
        "headers": ["Seq", "ID", "Dossier", "UF Resp", "Service", "Début", "Code", "Libellé"],
        "rows": rows,
        "context": {"dossier_id": dossier_id},
        "new_url": f"/venues/new?dossier_id={dossier_id}",
        "filters": filters,
        "actions": actions,
        "show_actions": True
    }

    return templates.TemplateResponse(request, "list.html", ctx)

@router.get("/new", response_class=HTMLResponse)
def new_venue(
    request: Request, 
    dossier_id: int | None = Query(None, description="ID du dossier parent (pré-rempli si fourni)"),
    session=Depends(get_session)
):
    next_seq = peek_next_sequence(session, "venue")
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    
    # Si dossier_id fourni en query param, pré-remplir le champ
    # Sinon, tenter de récupérer depuis le contexte
    prefill_dossier_id = dossier_id
    if prefill_dossier_id is None and hasattr(request.state, 'dossier_context') and request.state.dossier_context:
        prefill_dossier_id = request.state.dossier_context.id
    
    # Si toujours None, on ne peut pas créer de venue sans dossier
    if prefill_dossier_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Impossible de créer une venue : aucun dossier n'est spécifié.")
    
    # Récupérer la liste des UF disponibles pour l'EJ du dossier
    uf_options = []
    if prefill_dossier_id:
        dossier = session.get(Dossier, prefill_dossier_id)
        if dossier and dossier.entite_juridique_id:
            from app.models_structure import EntiteJuridique
            ej = session.get(EntiteJuridique, dossier.entite_juridique_id)
            if ej:
                # Récupérer toutes les UF de la structure
                from app.models_structure import UniteFonctionnelle
                ufs = session.exec(
                    select(UniteFonctionnelle).where(UniteFonctionnelle.service_id.is_not(None))
                ).all()
                # Filtrer les UF de l'EJ
                ufs_ej = [uf for uf in ufs if getattr(uf.service, 'pole', None) and getattr(uf.service.pole, 'entite_geo', None) and getattr(uf.service.pole.entite_geo, 'entite_juridique_id', None) == ej.id]
                uf_options = []
                for uf in ufs_ej:
                    label = uf.short_name if uf.short_name else uf.name
                    uf_options.append({"value": uf.identifier, "label": label})
    # Afficher le numéro de dossier (dossier_seq) si possible
    dossier_seq_value = ''
    if prefill_dossier_id:
        dossier = session.get(Dossier, prefill_dossier_id)
        if dossier:
            dossier_seq_value = dossier.dossier_seq
    fields = [
        {"label": "Numéro de dossier", "name": "dossier_seq", "type": "number", "required": True,
         "value": dossier_seq_value or '',
         "readonly": True,
         "help": "Numéro de dossier métier (dossier_seq)"},
        {"name": "dossier_id", "type": "hidden", "value": prefill_dossier_id or ''},
    {"label": "UF de responsabilité", "name": "uf_responsabilite", "type": "select", "required": True,
     "options": uf_options if uf_options else [{"value": "", "label": "Aucune UF disponible"}],
     "help": "Unité fonctionnelle responsable de la venue (choix dynamique selon l'établissement)"},
        {"label": "Début de venue", "name": "start_time", "type": "datetime-local", 
         "value": now_str, "required": True,
         "help": "Date et heure de début de la venue"},
        {"label": "Numéro de venue", "name": "venue_seq", "type": "number", 
         "value": next_seq,
         "readonly": True,
         "help": "Généré automatiquement si non renseigné"},
    ]
    return templates.TemplateResponse(request, "form.html", {"request": request, "title": "Nouvelle venue", "fields": fields})


@router.post("/new")
def create_venue(
    dossier_id: int = Form(...),
    uf_responsabilite: str = Form(...),
    start_time: str = Form(...),
    hospital_service: str = Form(None),
    assigned_location: str = Form(None),
    attending_provider: str = Form(None),
    bed: str = Form(None),
    room: str = Form(None),
    code: str = Form(None),
    label: str = Form(None),
    venue_seq: int | None = Form(None),
    managing_department: str = Form(None),
    physical_type: str = Form(None),
    operational_status: str = Form(None),
    session=Depends(get_session)
):
    start_dt = datetime.fromisoformat(start_time)
    seq = venue_seq or get_next_sequence(session, "venue")
    v = Venue(
        dossier_id=dossier_id,
        uf_responsabilite=uf_responsabilite,
        start_time=start_dt,
        venue_seq=seq,
    )
    session.add(v); session.commit()
    
    # Refresh with relationships for emit_to_senders
    session.refresh(v, ["dossier"])
    if v.dossier:
        session.refresh(v.dossier, ["patient"])
    
    emit_to_senders(v, "venue", session)
    return RedirectResponse(url="/venues", status_code=303)

@router.get("/{venue_id}", response_class=HTMLResponse)
def venue_detail(venue_id: int, request: Request, session=Depends(get_session)):
    v = session.get(Venue, venue_id)
    if not v:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    # Charger le dossier et le patient pour le contexte
    dossier = session.get(Dossier, v.dossier_id) if v.dossier_id else None
    patient = session.get(type(dossier.patient), dossier.patient_id) if dossier and dossier.patient_id else None
    return templates.TemplateResponse(request, "venue_detail.html", {
        "request": request,
        "venue": v,
        "dossier": dossier,
        "patient": patient
    })


@router.get("/{venue_id}/edit", response_class=HTMLResponse)
def edit_venue(venue_id: int, request: Request, session=Depends(get_session)):
    v = session.get(Venue, venue_id)
    if not v:
            return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    
    # Récupérer la liste des UF disponibles pour l'EJ du dossier
    uf_options = []
    if v.dossier_id:
        dossier = session.get(Dossier, v.dossier_id)
        if dossier and dossier.entite_juridique_id:
            from app.models_structure import EntiteJuridique
            ej = session.get(EntiteJuridique, dossier.entite_juridique_id)
            if ej:
                # Récupérer toutes les UF de la structure
                from app.models_structure import UniteFonctionnelle
                ufs = session.exec(
                    select(UniteFonctionnelle).where(UniteFonctionnelle.service_id.is_not(None))
                ).all()
                # Filtrer les UF de l'EJ
                ufs_ej = [uf for uf in ufs if getattr(uf.service, 'pole', None) and getattr(uf.service.pole, 'entite_geo', None) and getattr(uf.service.pole.entite_geo, 'entite_juridique_id', None) == ej.id]
                uf_options = [
                    {"value": uf.um_code, "label": f"{uf.um_code} - {uf.name}"} for uf in ufs_ej if uf.um_code
                ]
    
    fields = [
        {"label": "Dossier ID", "name": "dossier_id", "type": "number", "value": v.dossier_id, "required": True,
         "help": "ID du dossier existant dans la base"},
        {"label": "UF de responsabilité", "name": "uf_responsabilite", "type": "select", "value": v.uf_responsabilite, "required": True,
         "options": uf_options,
         "help": "Unité fonctionnelle responsable de la venue (choix dynamique selon l'établissement)"},
        {"label": "Début de venue", "name": "start_time", "type": "datetime-local", 
         "value": v.start_time.strftime('%Y-%m-%dT%H:%M') if v.start_time else '', "required": True,
         "help": "Date et heure de début de la venue"},
        {"label": "Numéro de séquence", "name": "venue_seq", "type": "number", 
         "value": v.venue_seq,
         "help": "Numéro de séquence unique de la venue"},
    ]
    return templates.TemplateResponse(request, "form.html", {"request": request, "title": "Modifier venue", "fields": fields, "action_url": f"/venues/{venue_id}/edit"})


@router.post("/{venue_id}/edit")
def update_venue(
    venue_id: int,
    dossier_id: int = Form(...),
    uf_responsabilite: str = Form(...),
    start_time: str = Form(...),
    hospital_service: str = Form(None),
    assigned_location: str = Form(None),
    attending_provider: str = Form(None),
    bed: str = Form(None),
    room: str = Form(None),
    code: str = Form(None),
    label: str = Form(None),
    venue_seq: int = Form(...),
    managing_department: str = Form(None),
    physical_type: str = Form(None),
    operational_status: str = Form(None),
    session=Depends(get_session),
    request: Request = None
):
    v = session.get(Venue, venue_id)
    if not v:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    v.dossier_id = dossier_id
    v.uf_responsabilite = uf_responsabilite
    v.start_time = datetime.fromisoformat(start_time)
    v.venue_seq = venue_seq
    session.add(v); session.commit()
    
    # Refresh with relationships for emit_to_senders
    session.refresh(v, ["dossier"])
    if v.dossier:
        session.refresh(v.dossier, ["patient"])
    
    emit_to_senders(v, "venue", session)
    return RedirectResponse(url="/venues", status_code=303)


@router.post("/{venue_id}/delete")
def delete_venue(venue_id: int, request: Request, session=Depends(get_session)):
    v = session.get(Venue, venue_id)
    if not v:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Venue introuvable"}, status_code=404)
    dossier_id = v.dossier_id  # Capture l'ID du dossier avant de supprimer
    
    # Refresh with relationships for emit_to_senders before deletion
    session.refresh(v, ["dossier"])
    if v.dossier:
        session.refresh(v.dossier, ["patient"])
    
    session.delete(v); session.commit()
    emit_to_senders(v, "venue", session)
    return RedirectResponse(url=f"/venues?dossier_id={dossier_id}", status_code=303)

