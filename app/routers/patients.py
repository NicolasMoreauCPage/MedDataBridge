import logging
from typing import Optional

from collections.abc import Mapping
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.dependencies.request_data import read_form_data
from app.models import Dossier, Patient
from app.models.identifiers import Identifier
from app.services import patients_service
from app.services.patients_service import PatientCreateSchema, PatientUpdateSchema
from app.services.scenario_identity_generator import (
    generate_patient_identity,
    identity_to_sample_data,
)
from app.services.vocabulary_lookup import get_vocabulary_options
from app.services.identifier_manager import map_identifier_type_to_hl7_code
from app.utils.flash import flash

def get_templates(request: Request):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patients",
    tags=["patients"],
)

@router.post("/api/patients", response_class=JSONResponse, summary="API for creating a patient")
def api_create_patient(
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
def list_patients(
    request: Request,
    name: str | None = Query(None),
    gender: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=25, le=100),
    session=Depends(get_session),
):
    """Displays the list of patients, filtered by the current GHT/EJ context."""
    ght_context = getattr(request.state, "ght_context", None)
    ej_context = getattr(request.state, "ej_context", None)
    # Allow bypassing context filtering via query param ?all=1
    show_all = str(request.query_params.get('all', '')).lower() in ('1', 'true', 'yes')
    
    query = select(Patient)
    if not show_all:
        if ej_context and getattr(ej_context, "id", None):
            ej_id = ej_context.id
            # Patients directly linked to the EJ OR having a Dossier linked to the EJ
            subq = select(Dossier.patient_id).where(Dossier.entite_juridique_id == ej_id)
            query = query.where(
                (Patient.entite_juridique_id == ej_id) | (Patient.id.in_(subq))
            )
        elif ght_context and getattr(ght_context, "id", None):
            query = query.where(Patient.ght_context_id == ght_context.id)

    if name:
        pattern = f"%{name.strip()}%"
        query = query.where(
            Patient.family.ilike(pattern) | Patient.given.ilike(pattern)
        )
    if gender:
        query = query.where(Patient.gender == gender)

    total_count = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(page, total_pages)
    patients = session.exec(
        query.order_by(Patient.family, Patient.given, Patient.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    # Si le contexte filtre à zéro patients, exposer un flag pour la bannière explicite
    context_filtered_empty = False
    if not patients and not show_all and (ej_context and getattr(ej_context, "id", None)):
        context_filtered_empty = True
    
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
        {"label": "Nom", "name": "name", "type": "text", "value": name or "", "placeholder": "Rechercher par nom"},
        {
            "label": "Genre", "name": "gender", "type": "select", "placeholder": "Tous",
            "value": gender or "",
            "options": [{"value": "male", "label": "Homme"}, {"value": "female", "label": "Femme"}]
        }
    ]
    actions = [
        {"type": "link", "label": "Export FHIR", "url": "/patients/export/fhir"},
        {"type": "link", "label": "Import FHIR", "url": "/patients/import/fhir"},
        {"type": "link", "label": "Fusionner deux patients (A40)", "url": "/patients/merge"},
    ]

    raw_query_params = getattr(request, "query_params", None)
    query_params = dict(raw_query_params) if isinstance(raw_query_params, Mapping) else {}
    query_params.pop("page", None)
    query_params.pop("page_size", None)
    query_params["page_size"] = str(page_size)
    encoded_params = urlencode(query_params)
    pagination = {
        "page": page,
        "page_size": page_size,
        "page_size_param": "page_size",
        "max_page_size": 100,
        "total_count": total_count,
        "total_pages": total_pages,
        "base_url": f"/patients?{encoded_params}" if encoded_params else "/patients?",
    }

    ctx = {
        "request": request, "title": "Patients", "breadcrumbs": breadcrumbs,
        "headers": ["ID", "ExtID", "Nom", "Date naiss.", "Genre"],
        "rows": rows, "new_url": "/patients/new", "filters": filters,
        "actions": actions, "show_actions": True, "pagination": pagination,
    }
    if context_filtered_empty:
        ctx["context_filtered_empty"] = True
    # Expose active context info to the template so the UI can show a banner
    if ej_context and getattr(ej_context, "id", None):
        ctx["active_context"] = {
            "kind": "ej",
            "name": getattr(ej_context, "name", ""),
            "clear_url": "/context/clear?kind=ej"
        }
    elif ght_context and getattr(ght_context, "id", None):
        ctx["active_context"] = {
            "kind": "ght",
            "name": getattr(ght_context, "name", ""),
            "clear_url": "/context/clear?kind=ght"
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
        "ins_type_options": get_vocabulary_options("semantic-ins-type"),
        "gender_options": get_vocabulary_options("administrative-gender-v2"),
        "country_options": get_vocabulary_options("country-codes"),
    })


@router.post("/{patient_id:int}/edit")
def update_patient_from_form(
    patient_id: int,
    request: Request,
    session: Session = Depends(get_session),
    form=Depends(read_form_data),
):
    """Handles the submission of the patient edit form."""
    patient = session.get(Patient, patient_id)
    if not patient:
        return HTMLResponse("Patient introuvable", status_code=404)

    is_ajax = request.headers.get('accept') == 'application/json'
    try:
        # Keep this list tied to the schema: every field exposed by the form is
        # persisted instead of silently dropping the PAM-relevant demographics.
        patient_update_data = PatientUpdateSchema(
            **{
                name: form.get(name)
                for name in PatientUpdateSchema.model_fields
                if name in form
            }
        )
        if not (patient_update_data.family or "").strip() or not (patient_update_data.given or "").strip():
            raise ValueError("Le nom et le prénom sont obligatoires.")

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


@router.get("/merge", response_class=HTMLResponse)
def merge_patients_form(
    request: Request,
    source_patient_id: Optional[int] = None,
    session=Depends(get_session),
):
    """Affiche le formulaire de fusion de deux patients (émission A40)."""
    patients = [
        patient
        for patient in session.exec(select(Patient).order_by(Patient.family, Patient.given)).all()
        if not (patient.family or "").startswith("[MERGED]")
        and not (patient.identifier or "").startswith("ARCHIVED-")
    ]
    templates = get_templates(request)
    return templates.TemplateResponse(request, "patient_merge_form.html", {
        "title": "Fusionner deux patients",
        "patients": patients,
        "source_patient_id": source_patient_id,
    })


@router.post("/merge")
def merge_patients_submit(
    request: Request,
    source_patient_id: int = Form(...),
    surviving_patient_id: int = Form(...),
    session: Session = Depends(get_session),
):
    """Traite la fusion de deux patients et déclenche l'émission A40."""
    from app.services.patient_merge import merge_patients

    ok, err = merge_patients(session, source_patient_id, surviving_patient_id)
    if ok:
        flash(request, "Patients fusionnés avec succès (message A40 émis)", "success")
        return RedirectResponse(url=f"/patients/{surviving_patient_id}", status_code=303)
    flash(request, f"Erreur lors de la fusion : {err}", "error")
    return RedirectResponse(url="/patients/merge", status_code=303)


@router.get("/{patient_id:int}/change-identifier", response_class=HTMLResponse)
def change_identifier_form(patient_id: int, request: Request, session=Depends(get_session)):
    """Affiche le formulaire de modification d'identifiant patient (émission A47)."""
    patient = session.get(Patient, patient_id)
    templates = get_templates(request)
    if not patient:
        return templates.TemplateResponse(request, "not_found.html", {"title": "Patient introuvable"}, status_code=404)
    current_identifier = session.exec(
        select(Identifier)
        .where(Identifier.patient_id == patient.id)
        .where(Identifier.value == patient.identifier)
        .where(Identifier.status == "active")
    ).first()
    return templates.TemplateResponse(request, "patient_change_identifier_form.html", {
        "title": "Modifier l'identifiant patient",
        "patient": patient,
        "current_identifier": current_identifier,
        "current_identifier_type": (
            map_identifier_type_to_hl7_code(current_identifier.type)
            if current_identifier
            else "PI"
        ) or "PI",
    })


@router.post("/{patient_id:int}/change-identifier")
def change_identifier_submit(
    patient_id: int,
    request: Request,
    new_value: str = Form(...),
    new_system: str = Form(None),
    new_oid: str = Form(None),
    new_type: str = Form("PI"),
    session: Session = Depends(get_session),
):
    """Traite la modification de l'identifiant principal d'un patient et déclenche l'émission A47."""
    from app.services.patient_merge import change_patient_identifier

    ok, err = change_patient_identifier(session, patient_id, new_value, new_system, new_oid, new_type)
    if ok:
        flash(request, "Identifiant patient modifié avec succès (message A47 émis)", "success")
        return RedirectResponse(url=f"/patients/{patient_id}", status_code=303)
    flash(request, f"Erreur lors de la modification : {err}", "error")
    return RedirectResponse(url=f"/patients/{patient_id}/change-identifier", status_code=303)


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
        "ins_type_options": get_vocabulary_options("semantic-ins-type"),
        "gender_options": get_vocabulary_options("administrative-gender-v2"),
        "country_options": get_vocabulary_options("country-codes"),
        "sample_data": sample_identity,
        "sample_prefilled": prefill_request,
    })

@router.post("/new")
def create_patient_from_form(
    request: Request,
    session: Session = Depends(get_session),
    # Form fields
    external_id: str = Form(None),
    family: str = Form(...),
    given: str = Form(...),
    middle: str = Form(None),
    prefix: str = Form(None),
    suffix: str = Form(None),
    birth_family: str = Form(None),
    birth_date: str = Form(None),
    gender: str = Form(None),
    address: str = Form(None),
    city: str = Form(None),
    state: str = Form(None),
    postal_code: str = Form(None),
    country: str = Form(None),
    phone: str = Form(None),
    mobile: str = Form(None),
    work_phone: str = Form(None),
    email: str = Form(None),
    birth_address: str = Form(None),
    birth_city: str = Form(None),
    birth_state: str = Form(None),
    birth_postal_code: str = Form(None),
    birth_country: str = Form(None),
    nir: str = Form(None),
    marital_status: str = Form(None),
    nationality: str = Form(None),
    identity_reliability_code: str = Form(None),
    mothers_maiden_name: str = Form(None),
    primary_care_provider: str = Form(None)
):
    """Handles the submission of the new patient form."""
    is_ajax = request.headers.get('accept') == 'application/json' if request else False
    try:
        patient_create_data = PatientCreateSchema(
            external_id=external_id,
            family=family,
            given=given,
            middle=middle,
            prefix=prefix,
            suffix=suffix,
            birth_family=birth_family,
            birth_date=birth_date,
            gender=gender,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            phone=phone,
            mobile=mobile,
            work_phone=work_phone,
            email=email,
            birth_address=birth_address,
            birth_city=birth_city,
            birth_state=birth_state,
            birth_postal_code=birth_postal_code,
            birth_country=birth_country,
            nir=nir,
            marital_status=marital_status,
            nationality=nationality,
            identity_reliability_code=identity_reliability_code,
            mothers_maiden_name=mothers_maiden_name,
            primary_care_provider=primary_care_provider
        )
        
        ght_context = getattr(request.state, "ght_context", None)
        ght_context_id = getattr(ght_context, "id", None)
        
        patient = patients_service.create_patient(
            session=session, patient_data=patient_create_data, ght_context_id=ght_context_id
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
