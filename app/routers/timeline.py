from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.db import get_session
from app.models import Patient, Dossier, Venue, Mouvement
from app.dependencies.ght import require_ght_context

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(
    prefix="/timeline",
    tags=["timeline"],
    dependencies=[Depends(require_ght_context)],
)


def _format_datetime(dt) -> str:
    """Format datetime for display"""
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    return dt.strftime("%d/%m/%Y %H:%M")


def _get_patient_events(session: Session, patient_id: int) -> List[Dict[str, Any]]:
    """Get all events for a patient"""
    events = []
    
    # Get patient
    patient = session.get(Patient, patient_id)
    if not patient:
        return events
    
    # Patient creation event
    if patient.birth_date:
        events.append({
            "type": "patient",
            "icon": "user",
            "color": "blue",
            "title": f"Patient {patient.family} {patient.given}",
            "description": f"Né(e) le {patient.birth_date}",
            "datetime": patient.birth_date,
            "entity_id": patient.id,
            "entity_type": "patient"
        })
    
    # Get all dossiers
    dossiers = session.exec(select(Dossier).where(Dossier.patient_id == patient_id)).all()
    
    for dossier in dossiers:
        # Admission event
        if dossier.admit_time:
            events.append({
                "type": "admission",
                "icon": "login",
                "color": "green",
                "title": f"Admission - Dossier #{dossier.dossier_seq}",
                "description": f"UF: {dossier.uf_responsabilite or 'N/A'}",
                "datetime": dossier.admit_time,
                "entity_id": dossier.id,
                "entity_type": "dossier"
            })
        
        # Get venues for this dossier
        venues = session.exec(select(Venue).where(Venue.dossier_id == dossier.id)).all()
        
        for venue in venues:
            # Venue start
            if venue.start_time:
                events.append({
                    "type": "venue",
                    "icon": "map-pin",
                    "color": "purple",
                    "title": f"Venue #{venue.venue_seq}",
                    "description": f"Location: {venue.code or venue.label or 'N/A'}",
                    "datetime": venue.start_time,
                    "entity_id": venue.id,
                    "entity_type": "venue"
                })
            
            # Get mouvements for this venue
            mouvements = session.exec(select(Mouvement).where(Mouvement.venue_id == venue.id)).all()
            
            for mouv in mouvements:
                if mouv.when:
                    events.append({
                        "type": "mouvement",
                        "icon": "activity",
                        "color": "orange",
                        "title": f"{mouv.movement_type or mouv.trigger_event}",
                        "description": f"Location: {mouv.location or 'N/A'}",
                        "datetime": mouv.when,
                        "entity_id": mouv.id,
                        "entity_type": "mouvement"
                    })
        
        # Discharge event
        if dossier.discharge_time:
            events.append({
                "type": "discharge",
                "icon": "logout",
                "color": "red",
                "title": f"Sortie - Dossier #{dossier.dossier_seq}",
                "description": f"Fin d'hospitalisation",
                "datetime": dossier.discharge_time,
                "entity_id": dossier.id,
                "entity_type": "dossier"
            })
    
    # Sort events by datetime (most recent first)
    events.sort(key=lambda x: x["datetime"] if isinstance(x["datetime"], datetime) else datetime.now(), reverse=True)
    
    return events


def _get_dossier_events(session: Session, dossier_id: int) -> List[Dict[str, Any]]:
    """Get all events for a dossier"""
    events = []
    
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        return events
    
    # Admission
    if dossier.admit_time:
        events.append({
            "type": "admission",
            "icon": "login",
            "color": "green",
            "title": f"Admission",
            "description": f"UF: {dossier.uf_responsabilite or 'N/A'}",
            "datetime": dossier.admit_time,
            "entity_id": dossier.id,
            "entity_type": "dossier"
        })
    
    # Venues
    venues = session.exec(select(Venue).where(Venue.dossier_id == dossier_id)).all()
    
    for venue in venues:
        if venue.start_time:
            events.append({
                "type": "venue",
                "icon": "map-pin",
                "color": "purple",
                "title": f"Venue #{venue.venue_seq}",
                "description": f"Location: {venue.code or venue.label or 'N/A'}",
                "datetime": venue.start_time,
                "entity_id": venue.id,
                "entity_type": "venue"
            })
        
        # Mouvements
        mouvements = session.exec(select(Mouvement).where(Mouvement.venue_id == venue.id)).all()
        for mouv in mouvements:
            if mouv.when:
                events.append({
                    "type": "mouvement",
                    "icon": "activity",
                    "color": "orange",
                    "title": f"{mouv.movement_type or mouv.trigger_event}",
                    "description": f"Location: {mouv.location or 'N/A'}",
                    "datetime": mouv.when,
                    "entity_id": mouv.id,
                    "entity_type": "mouvement"
                })
    
    # Discharge
    if dossier.discharge_time:
        events.append({
            "type": "discharge",
            "icon": "logout",
            "color": "red",
            "title": f"Sortie",
            "description": f"Fin d'hospitalisation",
            "datetime": dossier.discharge_time,
            "entity_id": dossier.id,
            "entity_type": "dossier"
        })
    
    events.sort(key=lambda x: x["datetime"] if isinstance(x["datetime"], datetime) else datetime.now(), reverse=True)
    return events


def _get_venue_events(session: Session, venue_id: int) -> List[Dict[str, Any]]:
    """Get all events for a venue"""
    events = []
    
    venue = session.get(Venue, venue_id)
    if not venue:
        return events
    
    # Venue start
    if venue.start_time:
        events.append({
            "type": "venue",
            "icon": "map-pin",
            "color": "purple",
            "title": f"Début venue #{venue.venue_seq}",
            "description": f"Location: {venue.code or venue.label or 'N/A'}",
            "datetime": venue.start_time,
            "entity_id": venue.id,
            "entity_type": "venue"
        })
    
    # Mouvements
    mouvements = session.exec(select(Mouvement).where(Mouvement.venue_id == venue_id)).all()
    for mouv in mouvements:
        if mouv.when:
            events.append({
                "type": "mouvement",
                "icon": "activity",
                "color": "orange",
                "title": f"{mouv.movement_type or mouv.trigger_event}",
                "description": f"Location: {mouv.location or 'N/A'}",
                "datetime": mouv.when,
                "entity_id": mouv.id,
                "entity_type": "mouvement"
            })
    
    events.sort(key=lambda x: x["datetime"] if isinstance(x["datetime"], datetime) else datetime.now(), reverse=True)
    return events


@router.get("/patient/{patient_id}", response_class=HTMLResponse)
def patient_timeline(
    request: Request,
    patient_id: int,
    session: Session = Depends(get_session)
):
    """Timeline view for a patient"""
    patient = session.get(Patient, patient_id)
    if not patient:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "message": "Patient non trouvé"}
        )
    
    events = _get_patient_events(session, patient_id)
    
    # Format datetime for display
    for event in events:
        event["datetime_display"] = _format_datetime(event["datetime"])
    
    breadcrumbs = [
        {"label": "Patients", "url": "/patients"},
        {"label": f"{patient.family} {patient.given}", "url": f"/patients/{patient_id}"},
        {"label": "Timeline", "url": f"/timeline/patient/{patient_id}"}
    ]
    
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "request": request,
            "title": f"Timeline - {patient.family} {patient.given}",
            "breadcrumbs": breadcrumbs,
            "events": events,
            "entity_type": "patient",
            "entity_id": patient_id,
            "entity_name": f"{patient.family} {patient.given}"
        }
    )


@router.get("/dossier/{dossier_id}", response_class=HTMLResponse)
def dossier_timeline(
    request: Request,
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """Timeline view for a dossier"""
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "message": "Dossier non trouvé"}
        )
    
    events = _get_dossier_events(session, dossier_id)
    
    # Format datetime for display
    for event in events:
        event["datetime_display"] = _format_datetime(event["datetime"])
    
    patient = session.get(Patient, dossier.patient_id) if dossier.patient_id else None
    
    breadcrumbs = [
        {"label": "Dossiers", "url": "/dossiers"}
    ]
    if patient:
        breadcrumbs.append({"label": f"{patient.family} {patient.given}", "url": f"/patients/{patient.id}"})
    breadcrumbs.extend([
        {"label": f"Dossier #{dossier.dossier_seq}", "url": f"/dossiers/{dossier_id}"},
        {"label": "Timeline", "url": f"/timeline/dossier/{dossier_id}"}
    ])
    
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "request": request,
            "title": f"Timeline - Dossier #{dossier.dossier_seq}",
            "breadcrumbs": breadcrumbs,
            "events": events,
            "entity_type": "dossier",
            "entity_id": dossier_id,
            "entity_name": f"Dossier #{dossier.dossier_seq}"
        }
    )


@router.get("/venue/{venue_id}", response_class=HTMLResponse)
def venue_timeline(
    request: Request,
    venue_id: int,
    session: Session = Depends(get_session)
):
    """Timeline view for a venue"""
    venue = session.get(Venue, venue_id)
    if not venue:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "message": "Venue non trouvée"}
        )
    
    events = _get_venue_events(session, venue_id)
    
    # Format datetime for display
    for event in events:
        event["datetime_display"] = _format_datetime(event["datetime"])
    
    dossier = session.get(Dossier, venue.dossier_id) if venue.dossier_id else None
    patient = session.get(Patient, dossier.patient_id) if dossier and dossier.patient_id else None
    
    breadcrumbs = [
        {"label": "Venues", "url": "/venues"}
    ]
    if patient:
        breadcrumbs.append({"label": f"{patient.family} {patient.given}", "url": f"/patients/{patient.id}"})
    if dossier:
        breadcrumbs.append({"label": f"Dossier #{dossier.dossier_seq}", "url": f"/dossiers/{dossier.id}"})
    breadcrumbs.extend([
        {"label": f"Venue #{venue.venue_seq}", "url": f"/venues/{venue_id}"},
        {"label": "Timeline", "url": f"/timeline/venue/{venue_id}"}
    ])
    
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "request": request,
            "title": f"Timeline - Venue #{venue.venue_seq}",
            "breadcrumbs": breadcrumbs,
            "events": events,
            "entity_type": "venue",
            "entity_id": venue_id,
            "entity_name": f"Venue #{venue.venue_seq}"
        }
    )
