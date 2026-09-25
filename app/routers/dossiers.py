

# --- ALL IMPORTS AT TOP ---
from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query, Request
import os
import logging
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import select, Session
from sqlalchemy.orm import selectinload
from sqlalchemy import String, func
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode
from collections.abc import Mapping
from app.db import get_session
from app.models import Dossier, Patient, DossierType, Venue, CCAMAct, NGAPAct, UCDAct, LPPAct
from app.services import dossiers_service
from app.services.dossiers_service import DossierCreateSchema, DossierUpdateSchema
from app.utils.flash import flash
from app.dependencies.ght import require_ght_context

logger = logging.getLogger(__name__)

# Router definition after imports
router = APIRouter(
    prefix="/dossiers",
    tags=["dossiers"],
    dependencies=[Depends(require_ght_context)]
)

# Separate router for routes that don't require GHT context
public_router = APIRouter(
    prefix="/dossiers",
    tags=["dossiers-public"],
)

# Separate router for API endpoints without GHT context requirement
api_router = APIRouter(
    prefix="/dossiers/api",
    tags=["dossiers-api"],
)



def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(
    prefix="/dossiers",
    tags=["dossiers"],
    dependencies=[Depends(require_ght_context)]
)

# GET endpoints remain as they are for now
@router.get("", response_class=HTMLResponse)
def list_dossiers(
    request: Request,
    patient_id: int | None = Query(None),
    dossier_type: str | None = Query(None),
    dossier_seq: int | None = Query(None),
    uf: str | None = Query(None, description="Filtrer par UF de responsabilité (contient)"),
    medecin: str | None = Query(None, alias="attending_provider", description="Filtrer par médecin responsable (contient)"),
    admit_from: str | None = Query(None, description="Filtrer par date d'admission à partir de (AAAA-MM-JJ)"),
    admit_to: str | None = Query(None, description="Filtrer par date d'admission jusqu'à (AAAA-MM-JJ)"),
    current_state: str | None = Query(None, description="Filtrer par état courant"),
    page: int = 1,
    page_size: int = 50,
    session=Depends(get_session)
):
    try:
        dossier_type_filter = DossierType(dossier_type) if dossier_type else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Type de dossier inconnu") from exc

    # Récupérer les contextes EG et EJ (EG a priorité s'il est défini)
    eg_context = getattr(request.state, "eg_context", None)
    ej_context = getattr(request.state, "ej_context", None)
    eg_id = getattr(eg_context, "id", None)
    ej_id = getattr(ej_context, "id", None) if not eg_id else None  # EJ seulement si pas d'EG
    
    dossier_filters = dict(
        ej_id=ej_id,
        eg_id=eg_id,
        patient_id=patient_id,
        dossier_type=dossier_type_filter,
        dossier_seq=dossier_seq,
        uf=uf,
        medecin=medecin,
        admit_from=admit_from,
        admit_to=admit_to,
        current_state=current_state,
    )

    page = max(1, page)
    page_size = min(max(page_size, 25), 100)
    total_count = dossiers_service.count_dossiers(session, **dossier_filters)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(page, total_pages)
    page_dossiers = dossiers_service.get_dossiers(
        session,
        **dossier_filters,
        offset=(page - 1) * page_size,
        limit=page_size,
    )

    # Quatre agrégations couvrent toute la page, indépendamment de sa taille.
    dossier_acts_count = {d.id: 0 for d in page_dossiers}
    dossier_ids = list(dossier_acts_count)
    if dossier_ids:
        for act_model in (CCAMAct, NGAPAct, UCDAct, LPPAct):
            counts = session.exec(
                select(act_model.dossier_id, func.count(act_model.id))
                .where(act_model.dossier_id.in_(dossier_ids))
                .group_by(act_model.dossier_id)
            ).all()
            for dossier_id, count in counts:
                dossier_acts_count[dossier_id] += count
    
    rows = [
        {
            "cells": [d.dossier_seq, d.id, d.patient_id, 
                      (d.venues[0].uf_responsabilite if d.venues and d.venues[0].uf_responsabilite else "N/A"),
                      getattr(d, 'dossier_type', DossierType.HOSPITALISE).value.capitalize(),
                      d.admit_time.strftime("%d/%m/%Y %H:%M") if d.admit_time else None,
                      d.discharge_time.strftime("%d/%m/%Y %H:%M") if d.discharge_time else None,
                      dossier_acts_count.get(d.id, 0)],
            "detail_url": f"/dossiers/{d.id}", "edit_url": f"/dossiers/{d.id}/edit", "cotation_url": f"/dossiers/{d.id}/cotation",
        } for d in page_dossiers
    ]
    actions = [
        {"type": "link", "label": "Export FHIR", "url": "/dossiers/export/fhir"},
        {"type": "link", "label": "Import FHIR", "url": "/dossiers/import/fhir"}
    ]

    filters = [
        {
            "label": "UF responsabilité",
            "name": "uf",
            "type": "text",
            "value": uf or "",
            "placeholder": "Ex : CARDIO"
        },
        {
            "label": "Médecin responsable",
            "name": "attending_provider",
            "type": "text",
            "value": medecin or "",
            "placeholder": "Nom du praticien"
        },
        {
            "label": "Type de dossier",
            "name": "dossier_type",
            "type": "select",
            "value": dossier_type_filter.value if dossier_type_filter else "",
            "placeholder": "Tous les types",
            "options": [
                {"value": dt.value, "label": dt.name.replace('_', ' ').capitalize()}
                for dt in DossierType
            ]
        },
        {
            "label": "Admission à partir du",
            "name": "admit_from",
            "type": "text",
            "value": admit_from or "",
            "placeholder": "AAAA-MM-JJ"
        },
        {
            "label": "Admission jusqu'au",
            "name": "admit_to",
            "type": "text",
            "value": admit_to or "",
            "placeholder": "AAAA-MM-JJ"
        },
        {
            "label": "État courant",
            "name": "current_state",
            "type": "text",
            "value": current_state or "",
            "placeholder": "Ex : Hospitalisé, EN_SALLE..."
        },
    ]

    raw_query_params = getattr(request, "query_params", None)
    query_params = dict(raw_query_params) if isinstance(raw_query_params, Mapping) else {}
    query_params.pop("page", None)
    query_params.pop("page_size", None)
    query_params["page_size"] = str(page_size)
    encoded_params = urlencode(query_params)
    request_url = getattr(request, "url", None)
    request_path = getattr(request_url, "path", None)
    base_url = (request_path if isinstance(request_path, str) else "/dossiers") + (
        f"?{encoded_params}" if encoded_params else "?"
    )
    pagination = {
        "page": page,
        "page_size": page_size,
        "page_size_param": "page_size",
        "max_page_size": 100,
        "total_count": total_count,
        "total_pages": total_pages,
        "base_url": base_url,
    }

    ctx = {"request": request, "title": "Dossiers", "headers": ["Seq", "ID", "Patient", "UF resp.", "Type", "Admission", "Sortie", "Actes"], "rows": rows, "new_url": "/dossiers/new", "filters": filters, "actions": actions, "show_actions": True, "pagination": pagination}
    return get_templates_with_filters(request).TemplateResponse(request, "list.html", ctx)

@public_router.get("/{dossier_id}", response_class=HTMLResponse)
def show_dossier(dossier_id: int, request: Request):
    from app.db import session_factory
    session = session_factory()
    try:
        dossier = dossiers_service.get_dossier(session, dossier_id)
        if not dossier:
            return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)

        # Charger les relations nécessaires
        patient = session.exec(
            select(Patient).where(Patient.id == dossier.patient_id)
        ).first()

        # Vérifier l'accès au dossier via le GHT (optionnel)
        ght_context = getattr(request.state, "ght_context", None)
        if ght_context:
            # Le dossier doit appartenir à une EJ du GHT, ou ne pas avoir d'EJ assignée
            from app.models_structure import EntiteJuridique
            ej_ids = session.exec(
                select(EntiteJuridique.id).where(EntiteJuridique.ght_context_id == ght_context.id)
            ).all()
            if dossier.entite_juridique_id is not None and dossier.entite_juridique_id not in ej_ids:
                return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)

        venues = session.exec(
            select(Venue).where(Venue.dossier_id == dossier_id).order_by(Venue.start_time)
        ).all()

        return get_templates_with_filters(request).TemplateResponse(
            request,
            "dossier_detail.html",
            {
                "request": request,
                "dossier": dossier,
                "patient": patient,
                "venues": venues,
            }
        )
    finally:
        session.close()

@public_router.get("/{dossier_id}/cotation", response_class=RedirectResponse)
def redirect_dossier_cotation(dossier_id: int):
    """Redirige vers la page de cotation moderne pour ce dossier"""
    return RedirectResponse(url=f"/cotation-modern?dossier_id={dossier_id}", status_code=302)

@router.get("/new", response_class=HTMLResponse)
def new_dossier(
    request: Request,
    patient_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    patient_context = getattr(request.state, "patient_context", None)
    if not patient_context and patient_id is not None:
        try:
            patient_context = session.get(Patient, int(patient_id))
        except (TypeError, ValueError):
            patient_context = None
        if patient_context:
            request.state.patient_context = patient_context
    if not patient_context:
        flash(request, "Sélectionnez d'abord le patient auquel rattacher le dossier.", level="info")
        return RedirectResponse("/patients", status_code=303)

    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    ej_id = getattr(getattr(request.state, "ej_context", None), "id", None)
    uf_options = dossiers_service.get_uf_options(session, ej_id) if ej_id else []
    dossier_type_opts = [{"value": dt.value, "label": dt.name.replace('_', ' ').capitalize()} for dt in DossierType]
    fields = [
        {"name": "uf_responsabilite", "label": "UF de responsabilité", "type": "select", "options": uf_options, "empty_message": "Aucune UF disponible. Sélectionnez d'abord un contexte EJ (Établissement Juridique) ou créez des structures organisationnelles."},
        {"name": "dossier_type", "label": "Type de dossier", "type": "select", "options": dossier_type_opts},
        {"name": "admit_time", "label": "Date d'admission", "type": "datetime-local", "value": now_str},
    ]
    # During tests include a deterministic current_state select so UI tests can exercise state transitions
    if os.getenv("TESTING"):
        # Options chosen to match values expected by workflow validation logic
        state_options = [
            {"value": "Pas de venue courante", "label": "Pas de venue courante"},
            {"value": "Hospitalisé", "label": "Hospitalisé"},
            {"value": "EN_SALLE", "label": "En salle"},
            {"value": "PRE_ADMIT", "label": "Pré-admission"},
        ]
        fields.append({"name": "current_state", "label": "État courant", "type": "select", "options": state_options, "value": "Pas de venue courante"})
        # Provide an event_code selector so tests can exercise transition validation
        event_options = [
            {"value": "A01", "label": "A01 - Admit"},
            {"value": "A02", "label": "A02 - Transfer"},
            {"value": "A03", "label": "A03 - Discharge"},
            {"value": "A06", "label": "A06 - Change attending"},
            {"value": "A07", "label": "A07 - Change attending"},
            {"value": "A12", "label": "A12 - Cancel Admission"},
            {"value": "A13", "label": "A13 - Cancel Discharge"},
            {"value": "A38", "label": "A38 - Invalid transition (test)"},
        ]
        fields.append({"name": "event_code", "label": "Code événement", "type": "select", "options": event_options})
    return get_templates_with_filters(request).TemplateResponse(request, "form.html", {"request": request, "title": "Nouveau dossier", "fields": fields})


@router.get("/new-wizard", response_class=HTMLResponse)
def new_dossier_wizard(
    request: Request,
    patient_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """Wizard d'admission guidée (Patient déjà sélectionné).

    Cette vue propose une expérience en 3 étapes côté UI mais s'appuie
    sur le POST existant `/dossiers/new` pour créer le dossier et la
    pré-admission en base. Aucune logique métier n'est dupliquée ici.
    """
    patient_context = getattr(request.state, "patient_context", None)
    if not patient_context and patient_id is not None:
        try:
            patient_context = session.get(Patient, int(patient_id))
        except (TypeError, ValueError):
            patient_context = None
        if patient_context:
            request.state.patient_context = patient_context
    if not patient_context:
        flash(request, "Sélectionnez d'abord le patient à admettre.", level="info")
        return RedirectResponse("/patients", status_code=303)

    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    ej_id = getattr(getattr(request.state, "ej_context", None), "id", None)
    uf_options = dossiers_service.get_uf_options(session, ej_id) if ej_id else []
    dossier_type_opts = [
        {"value": dt.value, "label": dt.name.replace("_", " ").capitalize()} for dt in DossierType
    ]

    ctx = {
        "request": request,
        "title": "Admission guidée",
        "patient": patient_context,
        "uf_options": uf_options,
        "dossier_type_opts": dossier_type_opts,
        "default_admit_time": now_str,
    }
    return get_templates_with_filters(request).TemplateResponse(request, "admission_wizard.html", ctx)

@router.post("/new")
def create_dossier(
    request: Request,
    uf_responsabilite: str = Form(None),
    dossier_type: str = Form("hospitalise"),
    admission_source: str = Form(None),
    attending_provider: str = Form(None),
    admit_time: str = Form(...),
    current_state: str = Form("Pas de venue courante"),
    session=Depends(get_session),
):
    patient_context = getattr(request.state, "patient_context", None)
    if not patient_context:
        flash(request, "Aucun patient sélectionné.", "error")
        return RedirectResponse("/patients", status_code=303)

    try:
        admit_dt = datetime.fromisoformat(admit_time)
        dossier_data = DossierCreateSchema(
            uf_responsabilite=uf_responsabilite, dossier_type=dossier_type,
            admission_source=admission_source, attending_provider=attending_provider,
            admit_time=admit_dt, current_state=current_state
        )
        dossiers_service.create_dossier_with_pre_admit_venue(
            session=session, dossier_data=dossier_data, patient=patient_context
        )
        flash(request, "Dossier et pré-admission créés avec succès.", "success")
        return RedirectResponse(url="/dossiers", status_code=303)
    except Exception as e:
        flash(request, f"Erreur lors de la création du dossier: {e}", "error")
        return RedirectResponse(url="/dossiers/new", status_code=303)

@router.get("/{dossier_id}/edit", response_class=HTMLResponse)
def edit_dossier(dossier_id: int, request: Request, session=Depends(get_session)):
    dossier = dossiers_service.get_dossier(session, dossier_id)
    if not dossier:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)
    fields = [
        {"label": "Patient ID", "name": "patient_id", "type": "number", "value": dossier.patient_id or 0},
        {"label": "Type de dossier", "name": "dossier_type", "type": "text", "value": dossier.dossier_type.value if dossier.dossier_type else ''},
        {"label": "Date d'admission", "name": "admit_time", "type": "datetime-local", "value": dossier.admit_time.strftime('%Y-%m-%dT%H:%M') if dossier.admit_time else ''},
        {"label": "Numéro de séquence", "name": "dossier_seq", "type": "number", "value": dossier.dossier_seq or 0},
    ]
    return get_templates_with_filters(request).TemplateResponse(request, "form.html", {"request": request, "title": "Modifier dossier", "fields": fields, "action_url": f"/dossiers/{dossier.id}/edit"})

@router.post("/{dossier_id}/edit")
def update_dossier(
    request: Request,
    dossier_id: int,
    patient_id: int = Form(...),
    uf_responsabilite: str = Form(...),
    dossier_type: str = Form(...),
    admission_source: str = Form(None),
    attending_provider: str = Form(None),
    admit_time: str = Form(...),
    dossier_seq: int = Form(...),
    session: Session = Depends(get_session),
):
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        flash(request, "Dossier introuvable.", "error")
        return RedirectResponse(url="/dossiers", status_code=404)

    try:
        update_data = DossierUpdateSchema(
            patient_id=patient_id,
            uf_responsabilite=uf_responsabilite,
            dossier_type=dossier_type,
            admission_source=admission_source,
            attending_provider=attending_provider,
            admit_time=datetime.fromisoformat(admit_time),
            dossier_seq=dossier_seq
        )
        dossiers_service.update_dossier(session=session, dossier=dossier, update_data=update_data)
        flash(request, "Dossier mis à jour avec succès.", "success")
    except Exception as e:
        flash(request, f"Erreur lors de la mise à jour: {e}", "error")

    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=303)

# ... (other endpoints like /delete, /replay, etc. remain unchanged for now)
@router.post("/{dossier_id}/delete")
def delete_dossier(dossier_id: int, request: Request, session=Depends(get_session)):
    dossier = dossiers_service.get_dossier(session, dossier_id)
    if not dossier:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"title": "Dossier introuvable"}, status_code=404)
    
    try:
        dossiers_service.delete_dossier(session, dossier)
        flash(request, "Dossier supprimé.", "success")
    except Exception as e:
        flash(request, f"Erreur lors de la suppression du dossier: {e}", "error")

    return RedirectResponse(url="/dossiers", status_code=303)

# API endpoints
@api_router.get("/dossiers", response_class=JSONResponse)
def api_list_dossiers(session=Depends(get_session)):
    """API endpoint to list all dossiers"""
    dossiers = dossiers_service.get_dossiers(session)
    return [
        {
            "id": d.id,
            "patient_id": d.patient_id,
            "dossier_type": d.dossier_type.value if d.dossier_type else None,
            "admit_time": d.admit_time.isoformat() if d.admit_time else None,
            "discharge_time": d.discharge_time.isoformat() if d.discharge_time else None,
        }
        for d in dossiers
    ]

@api_router.get("/search", response_class=JSONResponse)
def api_search_dossiers(
    q: str = Query(..., description="Terme de recherche (numéro dossier, nom patient)"),
    limit: int = Query(10, description="Nombre maximum de résultats"),
    session=Depends(get_session)
):
    """API endpoint pour rechercher des dossiers par numéro ou nom de patient"""
    try:
        from sqlalchemy import or_, func
        from app.models import Patient

        # Recherche par numéro de dossier ou nom/prénom patient
        stmt = select(Dossier).options(
            selectinload(Dossier.patient),
            selectinload(Dossier.medecin_responsable)
        ).where(
            or_(
                func.cast(Dossier.dossier_seq, String).like(f"%{q}%"),
                Dossier.patient.has(Patient.family.ilike(f"%{q}%")),
                Dossier.patient.has(Patient.given.ilike(f"%{q}%"))
            )
        ).limit(limit)

        result = session.exec(stmt)
        dossiers = result.all()

        return [
            {
                "id": d.id,
                "dossier_seq": d.dossier_seq,
                "patient": {
                    "family": d.patient.family,
                    "given": d.patient.given
                },
                "admit_time": d.admit_time.isoformat() if d.admit_time else None,
                "medecin_responsable": {
                    "nom": d.medecin_responsable.nom if d.medecin_responsable else None,
                    "prenom": d.medecin_responsable.prenom if d.medecin_responsable else None
                } if d.medecin_responsable else None,
                "current_state": d.current_state
            }
            for d in dossiers
        ]
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@api_router.get("/{dossier_id}", response_class=JSONResponse)
def api_get_dossier(
    dossier_id: int,
    session=Depends(get_session)
):
    """API endpoint pour récupérer les détails d'un dossier"""
    try:
        stmt = select(Dossier).options(
            selectinload(Dossier.patient),
            selectinload(Dossier.medecin_responsable)
        ).where(Dossier.id == dossier_id)

        result = session.exec(stmt)
        dossier = result.first()

        if not dossier:
            return JSONResponse(status_code=404, content={"detail": "Dossier non trouvé"})

        return {
            "id": dossier.id,
            "dossier_seq": dossier.dossier_seq,
            "patient": {
                "family": dossier.patient.family,
                "given": dossier.patient.given,
                "birth_date": dossier.patient.birth_date.isoformat() if dossier.patient.birth_date else None
            },
            "admit_time": dossier.admit_time.isoformat() if dossier.admit_time else None,
            "discharge_time": dossier.discharge_time.isoformat() if dossier.discharge_time else None,
            "dossier_type": dossier.dossier_type.value if dossier.dossier_type else None,
            "medecin_responsable": {
                "nom": dossier.medecin_responsable.nom if dossier.medecin_responsable else None,
                "prenom": dossier.medecin_responsable.prenom if dossier.medecin_responsable else None
            } if dossier.medecin_responsable else None,
            "current_state": dossier.current_state,
            "uf_responsabilite": dossier.uf_responsabilite
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@api_router.post("/dossiers", response_class=JSONResponse, summary="API for creating a dossier")
def api_create_dossier(
    patient_id: int = Body(...),
    dossier_type: str = Body("hospitalise"),
    admit_time: str = Body(...),
    uf_responsabilite: str = Body(None),
    admission_source: str = Body(None),
    attending_provider: str = Body(None),
    current_state: str = Body("Pas de venue courante"),
    session=Depends(get_session)
):
    """API REST endpoint to create a dossier, typically used by integration tests."""
    try:
        from datetime import datetime
        # Handle 'Z' suffix for UTC timezone which is not supported by fromisoformat
        if admit_time.endswith('Z'):
            admit_time = admit_time[:-1] + '+00:00'
        admit_dt = datetime.fromisoformat(admit_time)
        patient = session.get(Patient, patient_id)
        if not patient:
            return JSONResponse(status_code=404, content={"detail": "Patient not found"})
        
        dossier_data = DossierCreateSchema(
            uf_responsabilite=uf_responsabilite,
            dossier_type=dossier_type,
            admission_source=admission_source,
            attending_provider=attending_provider,
            admit_time=admit_dt,
            current_state=current_state
        )
        dossier = dossiers_service.create_dossier_with_pre_admit_venue(
            session=session, dossier_data=dossier_data, patient=patient
        )
        return {"id": dossier.id, "dossier_seq": dossier.dossier_seq}
    except Exception as e:
        logger.error(f"API dossier creation failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": str(e)})
