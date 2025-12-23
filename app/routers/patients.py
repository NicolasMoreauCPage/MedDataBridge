from sqlmodel import Session
import logging
from fastapi import APIRouter, Depends, Request, Form, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlmodel import select
from typing import Optional

logger = logging.getLogger(__name__)

from app.db import get_session
from app.schemas.patient import PatientFormData
from app.services import patients_service
from app.services.patients_service import PatientCreateSchema, PatientUpdateSchema
from app.services.scenario_identity_generator import (
    generate_patient_identity,
    identity_to_sample_data,
)
from app.services.vocabulary_lookup import get_vocabulary_options
from app.utils.flash import flash
from app.models import Patient

def get_templates(request: Request):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

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
            "cells": [p.id, p.identifier, f"{p.family} {p.given}", p.birth_date, p.gender],
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
    patient_id: int,
    family: str = Form(...),
    given: str = Form(...),
    birth_date: str = Form(None),
    gender: str = Form(None),
    identifier: str = Form(None),
    request: Request = None,
    session: Session = Depends(get_session)
):
    """Handles the submission of the patient edit form."""
    patient = session.get(Patient, patient_id)
    if not patient:
        return HTMLResponse("Patient introuvable", status_code=404)

    is_ajax = request.headers.get('accept') == 'application/json' if request else False
    try:
        patient_update_data = PatientUpdateSchema(
            identifier=identifier,
            family=family,
            given=given,
            birth_date=birth_date,
            gender=gender
        )

        patients_service.update_patient(session=session, patient=patient, patient_data=patient_update_data)
        flash(request, "Patient mis à jour avec succès", "success")
        return RedirectResponse(url=f"/patients/{patient_id}", status_code=303)
    except Exception as e:
        logger.error(f"Patient update failed: {e}", exc_info=True)
        if is_ajax:
            return JSONResponse(status_code=500, content={"detail": str(e)})
        flash(request, f"Erreur lors de la mise à jour: {str(e)}", "error")
        return RedirectResponse(url=f"/patients/{patient_id}/edit", status_code=303)


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


@router.get("/sample-identity", response_class=JSONResponse)
def generate_sample_identity():
    """Expose une identité patient réaliste pour pré-remplir le formulaire côté UI."""
    sample_identity = identity_to_sample_data(generate_patient_identity())
    return {"sample_data": sample_identity}

@router.get("/new", response_class=HTMLResponse)
def new_patient_form(request: Request):
    """Displays the form to create a new patient."""
    templates = get_templates(request)
    prefill_request = request.query_params.get("prefill") == "1"
    sample_identity = identity_to_sample_data(generate_patient_identity()) if prefill_request else None
    return templates.TemplateResponse(request, "patient_form.html", {
        "title": "Nouveau patient", "patient": None, "action_url": "/patients/new",
        "identity_reliability_options": get_vocabulary_options("identity-reliability-rniv"),
        "marital_status_options": get_vocabulary_options("marital-status"),
        "ins_type_options": get_vocabulary_options("ins-type"),
        "gender_options": get_vocabulary_options("administrative-gender-v2"),
        "country_options": get_vocabulary_options("country-codes"),
        "sample_data": sample_identity,
        "sample_prefilled": prefill_request,
    })

@router.post("/new")
async def create_patient_from_form(
    patient_data: PatientFormData = Depends(),
    request: Request = None,
    session: Session = Depends(get_session)
):
    """Handles the submission of the new patient form."""
    is_ajax = request.headers.get('accept') == 'application/json' if request else False
    try:
        patient_create_data = PatientCreateSchema(
            external_id=patient_data.external_id,
            family=patient_data.family,
            given=patient_data.given,
            middle=patient_data.middle,
            prefix=patient_data.prefix,
            suffix=patient_data.suffix,
            birth_family=patient_data.birth_family,
            birth_date=patient_data.birth_date,
            gender=patient_data.gender,
            address=patient_data.address,
            city=patient_data.city,
            state=patient_data.state,
            postal_code=patient_data.postal_code,
            country=patient_data.country,
            phone=patient_data.phone,
            mobile=patient_data.mobile,
            work_phone=patient_data.work_phone,
            email=patient_data.email,
            birth_address=patient_data.birth_address,
            birth_city=patient_data.birth_city,
            birth_state=patient_data.birth_state,
            birth_postal_code=patient_data.birth_postal_code,
            birth_country=patient_data.birth_country,
            nir=patient_data.nir,
            marital_status=patient_data.marital_status,
            nationality=patient_data.nationality,
            identity_reliability_code=patient_data.identity_reliability_code,
            mothers_maiden_name=patient_data.mothers_maiden_name,
            primary_care_provider=patient_data.primary_care_provider
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
