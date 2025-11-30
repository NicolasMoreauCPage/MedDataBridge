from sqlmodel import Session
import logging
from fastapi import APIRouter, Depends, Request, Form, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlmodel import select

from app.db import get_session
from app.dependencies.ght import require_ght_context
from app.models import Patient, DossierType
from app.routers.contacts import get_templates
from app.services import patients_service
from app.services.patients_service import PatientCreateSchema, PatientUpdateSchema
from app.services.vocabulary_lookup import get_vocabulary_options
from app.utils.flash import flash

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patients",
    tags=["patients"],
)

@router.post("/api/patients", response_class=JSONResponse, summary="API for creating a patient")
async def api_create_patient(
    family: str = Body(...),
    given: str = Body(None),
    birth_date: str = Body(None),
    session=Depends(get_session)
):
    """API REST endpoint to create a patient, typically used by integration tests."""
    try:
        patient_data = PatientCreateSchema(family=family, given=given, birth_date=birth_date)
        # REMARQUE: ght_context is not available in this API-only context
        patient = patients_service.create_patient(session=session, patient_data=patient_data)
        return {"id": patient.id, "family": patient.family, "given": patient.given, "birth_date": patient.birth_date}
    except Exception as e:
        logger.error(f"API patient creation failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": str(e)})

@router.get("", response_class=HTMLResponse)
def list_patients(request: Request, session=Depends(get_session)):
    """Displays the list of patients, filtered by the current GHT/EJ context."""
    ght_context = getattr(request.state, "ght_context", None)
    ej_context = getattr(request.state, "ej_context", None)
    
    query = select(Patient)
    if ej_context and getattr(ej_context, "id", None):
        query = query.where(Patient.entite_juridique_id == ej_context.id)
    elif ght_context and getattr(ght_context, "id", None):
        query = query.where(Patient.ght_context_id == ght_context.id)
        
    patients = session.exec(query).all()
    
    rows = [
        {
            "cells": [p.id, p.external_id, f"{p.family} {p.given}", p.birth_date, p.gender],
            "detail_url": f"/patients/{p.id}",
            "context_url": f"/context/patient/{p.id}",
            "timeline_url": f"/timeline/patient/{p.id}",
            "edit_url": f"/patients/{p.id}/edit",
            "delete_url": f"/patients/{p.id}/delete"
        }
        for p in patients
    ]
    breadcrumbs = [{"label": "Patients", "url": "/patients"}]
    filters = [
        {"label": "Nom", "name": "name", "type": "text", "placeholder": "Rechercher par nom"},
        {
            "label": "Genre", "name": "gender", "type": "select", "placeholder": "Tous",
            "options": [{"value": "male", "label": "Homme"}, {"value": "female", "label": "Femme"}]
        }
    ]
    actions = [
        {"type": "link", "label": "Export FHIR", "url": "/patients/export/fhir"},
        {"type": "link", "label": "Import FHIR", "url": "/patients/import/fhir"}
    ]

    ctx = {
        "request": request, "title": "Patients", "breadcrumbs": breadcrumbs,
        "headers": ["ID", "ExtID", "Nom", "Date naiss.", "Genre"],
        "rows": rows, "new_url": "/patients/new", "filters": filters,
        "actions": actions, "show_actions": True
    }
    
    templates = get_templates(request)
    return templates.TemplateResponse(request, "list.html", ctx)


@router.get("/{patient_id:int}", response_class=HTMLResponse)
def patient_detail(patient_id: int, request: Request, session=Depends(get_session)):
    """Displays the details of a single patient and their related records."""
    p = session.get(Patient, patient_id)
    templates = get_templates(request)
    if not p:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)

    request.session["patient_id"] = p.id

    # This N+1 query pattern should be refactored into a service function in the future.
    dossiers = session.exec(select(Dossier).where(Dossier.patient_id == p.id)).all() if p.dossiers else []
    for dossier in dossiers:
        dossier.venues = session.exec(select(type(dossier.venues[0])).where(type(dossier.venues[0]).dossier_id == dossier.id)).all() if dossier.venues else []
        for venue in dossier.venues:
            venue.mouvements = session.exec(select(type(venue.mouvements[0])).where(type(venue.mouvements[0]).venue_id == venue.id)).all() if venue.mouvements else []

    return templates.TemplateResponse(request, "patient_detail.html", {
        "patient": p, "dossiers": dossiers
    })


@router.get("/{patient_id:int}/edit", response_class=HTMLResponse)
def edit_patient(patient_id: int, request: Request, session=Depends(get_session)):
    """Displays the form to edit an existing patient."""
    p = session.get(Patient, patient_id)
    templates = get_templates(request)
    if not p:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)
    
    return templates.TemplateResponse(request, "patient_form.html", {
        "title": "Modifier patient", "patient": p, "action_url": f"/patients/{patient_id}/edit",
        "identity_reliability_options": get_vocabulary_options("identity-reliability-rniv"),
        "marital_status_options": get_vocabulary_options("marital-status"),
        "ins_type_options": get_vocabulary_options("ins-type"),
        "gender_options": get_vocabulary_options("administrative-gender-v2"),
        "country_options": get_vocabulary_options("country-codes"),
    })


@router.post("/{patient_id:int}/edit")
def update_patient_from_form(
    patient_id: int, session: Session = Depends(get_session),
    # Form fields are captured here and passed to the service
    external_id: str = Form(None), family: str = Form(...), given: str = Form(...),
    birth_date: str = Form(None), gender: str = Form(None), middle: str = Form(None),
    prefix: str = Form(None), suffix: str = Form(None), birth_family: str = Form(None),
    address: str = Form(None), city: str = Form(None), state: str = Form(None),
    postal_code: str = Form(None), country: str = Form(None), phone: str = Form(None),
    mobile: str = Form(None), work_phone: str = Form(None), email: str = Form(None),
    birth_address: str = Form(None), birth_city: str = Form(None), birth_state: str = Form(None),
    birth_postal_code: str = Form(None), birth_country: str = Form(None),
    marital_status: str = Form(None), mothers_maiden_name: str = Form(None),
    primary_care_provider: str = Form(None), nir: str = Form(None),
    nationality: str = Form(None), identity_reliability_code: str = Form(None),
    request: Request = None,
):
    """Handles the submission of the patient edit form."""
    patient = session.get(Patient, patient_id)
    if not patient:
        return HTMLResponse("Patient introuvable", status_code=404)

    update_data = PatientUpdateSchema(
        external_id=external_id, family=family, given=given, birth_date=birth_date,
        gender=gender, middle=middle, prefix=prefix, suffix=suffix, birth_family=birth_family,
        address=address, city=city, state=state, postal_code=postal_code, country=country,
        phone=phone, mobile=mobile, work_phone=work_phone, email=email,
        birth_address=birth_address, birth_city=birth_city, birth_state=birth_state,
        birth_postal_code=birth_postal_code, birth_country=birth_country,
        marital_status=marital_status, mothers_maiden_name=mothers_maiden_name,
        primary_care_provider=primary_care_provider, nir=nir, nationality=nationality,
        identity_reliability_code=identity_reliability_code
    )
    
    patients_service.update_patient(session=session, patient=patient, patient_data=update_data)
    flash(request, "Patient mis à jour avec succès", "success")
    return RedirectResponse(url=f"/patients/{patient_id}", status_code=303)


@router.post("/{patient_id:int}/delete")
def delete_patient(patient_id: int, request: Request, session=Depends(get_session)):
    """Deletes a patient."""
    p = session.get(Patient, patient_id)
    if not p:
        return HTMLResponse("Patient introuvable", status_code=404)
    session.delete(p)
    session.commit()
    flash(request, f"Patient {p.family} {p.given} supprimé.", "success")
    return RedirectResponse(url="/patients", status_code=303)

@router.get("/new", response_class=HTMLResponse)
def new_patient_form(request: Request):
    """Displays the form to create a new patient."""
    templates = get_templates(request)
    return templates.TemplateResponse(request, "patient_form.html", {
        "title": "Nouveau patient", "patient": None, "action_url": "/patients/new",
        "identity_reliability_options": get_vocabulary_options("identity-reliability-rniv"),
        "marital_status_options": get_vocabulary_options("marital-status"),
        "ins_type_options": get_vocabulary_options("ins-type"),
        "gender_options": get_vocabulary_options("administrative-gender-v2"),
        "country_options": get_vocabulary_options("country-codes"),
    })

@router.post("/new")
async def create_patient_from_form(
    request: Request, session: Session = Depends(get_session),
    # Form fields are captured here to be passed to the service
    external_id: str = Form(None), family: str = Form(...), given: str = Form(...),
    middle: str = Form(None), prefix: str = Form(None), suffix: str = Form(None),
    birth_family: str = Form(None), birth_date: str = Form(None), gender: str = Form(None),
    address: str = Form(None), city: str = Form(None), state: str = Form(None),
    postal_code: str = Form(None), country: str = Form(None), phone: str = Form(None),
    mobile: str = Form(None), work_phone: str = Form(None), email: str = Form(None),
    birth_address: str = Form(None), birth_city: str = Form(None), birth_state: str = Form(None),
    birth_postal_code: str = Form(None), birth_country: str = Form(None),
    nir: str = Form(None), marital_status: str = Form(None), nationality: str = Form(None),
    identity_reliability_code: str = Form(None), mothers_maiden_name: str = Form(None),
    primary_care_provider: str = Form(None),
):
    """Handles the submission of the new patient form."""
    is_ajax = request.headers.get('accept') == 'application/json'
    try:
        patient_data = PatientCreateSchema(
            external_id=external_id, family=family, given=given, middle=middle, prefix=prefix,
            suffix=suffix, birth_family=birth_family, birth_date=birth_date, gender=gender,
            address=address, city=city, state=state, postal_code=postal_code, country=country,
            phone=phone, mobile=mobile, work_phone=work_phone, email=email,
            birth_address=birth_address, birth_city=birth_city, birth_state=birth_state,
            birth_postal_code=birth_postal_code, birth_country=birth_country, nir=nir,
            marital_status=marital_status, nationality=nationality,
            identity_reliability_code=identity_reliability_code,
            mothers_maiden_name=mothers_maiden_name,
            primary_care_provider=primary_care_provider
        )
        
        ght_context = getattr(request.state, "ght_context", None)
        ght_context_id = getattr(ght_context, "id", None)
        
        patient = patients_service.create_patient(
            session=session, patient_data=patient_data, ght_context_id=ght_context_id
        )
        flash(request, f"Patient {patient.given} {patient.family} créé avec succès", "success")

        if is_ajax:
            return {"status": "success", "message": "Patient créé", "redirect": "/patients"}
        return RedirectResponse(url="/patients", status_code=303)

    except Exception as e:
        logger.error(f"Patient creation from form failed: {e}", exc_info=True)
        session.rollback()
        flash(request, f"Erreur lors de la création du patient: {e}", "error")
        if is_ajax:
            return {"status": "error", "message": str(e)}
        return RedirectResponse(url="/patients/new", status_code=303)
