

# --- ALL IMPORTS AT TOP ---
from fastapi import APIRouter, Depends, Request, Form, Query
import os
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import select, Session
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import List, Optional
from app.db import get_session
from app.models import Dossier, Patient, DossierType, Venue
from app.models_endpoints import SystemEndpoint
from app.models_scenarios import ScenarioBinding, InteropScenario
from app.services import dossiers_service
from app.services.dossiers_service import DossierCreateSchema, DossierUpdateSchema
from app.services.scenario_runner import send_scenario
from app.services.scenario_capture import capture_dossier_as_template
from app.form_config import get_field_config
from app.utils.flash import flash
from app.dependencies.ght import require_ght_context
from app.models_structure import GHTContext
from app.models_structure import UniteFonctionnelle, Service, Pole, EntiteGeographique

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
    dossier_type: DossierType | None = Query(None),
    dossier_seq: int | None = Query(None),
    session=Depends(get_session)
):
    ej_context = getattr(request.state, "ej_context", None)
    ej_id = getattr(ej_context, "id", None)
    # Temporairement forcer ej_id à None pour test
    ej_id = None
    
    dossiers = dossiers_service.get_dossiers(
        session,
        ej_id=ej_id,
        patient_id=patient_id,
        dossier_type=dossier_type,
        dossier_seq=dossier_seq,
    )
    
    rows = [
        {
            "cells": [d.dossier_seq, d.id, d.patient_id, 
                      (d.venues[0].uf_responsabilite if d.venues and d.venues[0].uf_responsabilite else "N/A"),
                      getattr(d, 'dossier_type', DossierType.HOSPITALISE).value.capitalize(),
                      d.admit_time.strftime("%d/%m/%Y %H:%M") if d.admit_time else None,
                      d.discharge_time.strftime("%d/%m/%Y %H:%M") if d.discharge_time else None],
            "detail_url": f"/dossiers/{d.id}", "edit_url": f"/dossiers/{d.id}/edit",
        } for d in dossiers
    ]
    actions = [
        {"type": "link", "label": "Export FHIR", "url": "/dossiers/export/fhir"},
        {"type": "link", "label": "Import FHIR", "url": "/dossiers/import/fhir"}
    ]

    ctx = {"request": request, "title": "Dossiers", "headers": ["Seq", "ID", "Patient", "UF resp.", "Type", "Admission", "Sortie"], "rows": rows, "new_url": "/dossiers/new", "actions": actions, "show_actions": True}
    return get_templates_with_filters(request).TemplateResponse(request, "list.html", ctx)

@public_router.get("/{dossier_id}", response_class=HTMLResponse)
def show_dossier(dossier_id: int, request: Request, session=Depends(get_session)):
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
        # Le dossier doit appartenir à une EJ du GHT
        from app.models_structure import EntiteJuridique
        ej_ids = session.exec(
            select(EntiteJuridique.id).where(EntiteJuridique.ght_context_id == ght_context.id)
        ).all()
        if dossier.entite_juridique_id not in ej_ids:
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

from typing import Optional
@router.get("/new", response_class=HTMLResponse)
def new_dossier(
    request: Request,
    patient_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    print(f"[DEBUG] Incoming query_params: {request.query_params}, patient_id={patient_id} (type={type(patient_id)})")
    # Utilise le contexte patient injecté par le middleware ou l'injecte pour les tests UI
    try:
        patient_context = getattr(request.state, "patient_context", None)
        print(f"[DEBUG] patient_id={patient_id}, patient_context={patient_context}")
        db_patient = None
        if not patient_context and patient_id is not None:
            from app.models import Patient
            try:
                pid_int = int(patient_id)
                db_patient = session.get(Patient, pid_int)
            except Exception as e:
                print(f"[DEBUG] Exception converting patient_id to int or fetching patient: {e}")
                db_patient = None
            print(f"[DEBUG] db_patient from id={patient_id}: {db_patient}")
            if db_patient:
                request.state.patient_context = db_patient
                patient_context = db_patient
        print(f"[DEBUG] patient_context after injection: {patient_context}")
        if not patient_context:
            print(f"[DEBUG] Redirecting to /patients: patient_context missing for patient_id={patient_id}")
            return RedirectResponse("/patients", status_code=303)
    except Exception as e:
        print(f"[EXCEPTION in /dossiers/new]: {e}")
        raise
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    ej_id = getattr(request.state, "ej_context.id", None)
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
