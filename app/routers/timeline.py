from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import Session, select

from app.db import get_session
from app.models import Patient, Dossier, Venue, Mouvement
from app.dependencies.ght import require_ght_context


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

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
        except ValueError:
            return dt
    return dt.strftime("%d/%m/%Y %H:%M")


@dataclass
class TimelineGraph:
    """Entities used to render a timeline, loaded with bounded query counts."""

    dossiers: List[Dossier]
    venues: List[Venue]
    mouvements: List[Mouvement]


def _load_timeline_graph(session: Session, dossiers: List[Dossier]) -> TimelineGraph:
    """Load venues then mouvements in bulk for a list of dossiers.

    The old implementation performed one query per dossier and one query per
    venue. A patient timeline with *D* dossiers and *V* venues therefore needed
    ``2 + D + V`` queries before rendering. This helper uses at most two queries
    after the dossiers have been selected.
    """
    dossier_ids = [dossier.id for dossier in dossiers if dossier.id is not None]
    if not dossier_ids:
        return TimelineGraph(dossiers=dossiers, venues=[], mouvements=[])

    venues = session.exec(
        select(Venue).where(Venue.dossier_id.in_(dossier_ids))
    ).all()
    venue_ids = [venue.id for venue in venues if venue.id is not None]
    mouvements = (
        session.exec(select(Mouvement).where(Mouvement.venue_id.in_(venue_ids))).all()
        if venue_ids
        else []
    )
    return TimelineGraph(dossiers=dossiers, venues=venues, mouvements=mouvements)


def _load_patient_timeline_graph(session: Session, patient_id: int) -> tuple[Patient | None, TimelineGraph]:
    """Load the patient and all timeline entities without N+1 queries."""
    patient = session.get(Patient, patient_id)
    if patient is None:
        return None, TimelineGraph(dossiers=[], venues=[], mouvements=[])
    dossiers = session.exec(
        select(Dossier).where(Dossier.patient_id == patient_id)
    ).all()
    return patient, _load_timeline_graph(session, dossiers)


def _build_patient_events(patient: Patient, graph: TimelineGraph) -> List[Dict[str, Any]]:
    """Build patient events from a preloaded timeline graph."""
    events = []

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
    
    venues_by_dossier: dict[int, list[Venue]] = defaultdict(list)
    for venue in graph.venues:
        venues_by_dossier[venue.dossier_id].append(venue)
    mouvements_by_venue: dict[int, list[Mouvement]] = defaultdict(list)
    for mouvement in graph.mouvements:
        mouvements_by_venue[mouvement.venue_id].append(mouvement)

    for dossier in graph.dossiers:
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
        
        for venue in venues_by_dossier[dossier.id]:
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
            
            for mouv in mouvements_by_venue[venue.id]:
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
                "description": "Fin d'hospitalisation",
                "datetime": dossier.discharge_time,
                "entity_id": dossier.id,
                "entity_type": "dossier"
            })
    
    # Sort events by datetime (most recent first)
    events.sort(key=lambda x: x["datetime"] if isinstance(x["datetime"], datetime) else datetime.now(), reverse=True)
    
    return events


def _get_patient_events(session: Session, patient_id: int) -> List[Dict[str, Any]]:
    """Get all events for a patient.

    Kept as a small public helper for existing callers; route handlers should
    reuse ``_load_patient_timeline_graph`` when they also render entity lists.
    """
    patient, graph = _load_patient_timeline_graph(session, patient_id)
    return _build_patient_events(patient, graph) if patient else []


def _build_dossier_events(dossier: Dossier, graph: TimelineGraph) -> List[Dict[str, Any]]:
    """Build dossier events from a preloaded timeline graph."""
    events = []
    
    # Admission
    if dossier.admit_time:
        # Récupérer l'UF depuis la première venue du dossier
        uf_resp = "N/A"
        if graph.venues and graph.venues[0].uf_responsabilite:
            uf_resp = graph.venues[0].uf_responsabilite
        
        events.append({
            "type": "admission",
            "icon": "login",
            "color": "green",
            "title": "Admission",
            "description": f"UF: {uf_resp}",
            "datetime": dossier.admit_time,
            "entity_id": dossier.id,
            "entity_type": "dossier"
        })
    
    # Venues
    mouvements_by_venue: dict[int, list[Mouvement]] = defaultdict(list)
    for mouvement in graph.mouvements:
        mouvements_by_venue[mouvement.venue_id].append(mouvement)

    for venue in graph.venues:
        if venue.start_time:
            events.append({
                "type": "venue",
                "icon": "map-pin",
                "color": "purple",
                "title": f"Venue #{venue.venue_seq}",
                "description": f"UF: {venue.uf_responsabilite or 'N/A'}",
                "datetime": venue.start_time,
                "entity_id": venue.id,
                "entity_type": "venue"
            })
        
        for mouv in mouvements_by_venue[venue.id]:
            if mouv.when:
                # Simplifier le titre sans movement_type_options
                title = mouv.movement_type or mouv.trigger_event or "Mouvement"
                events.append({
                    "type": "mouvement",
                    "icon": "activity",
                    "color": "orange",
                    "title": title,
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
            "title": "Sortie",
            "description": "Fin d'hospitalisation",
            "datetime": dossier.discharge_time,
            "entity_id": dossier.id,
            "entity_type": "dossier"
        })
    
    events.sort(key=lambda x: x["datetime"] if isinstance(x["datetime"], datetime) else datetime.now(), reverse=True)
    return events


def _get_dossier_events(session: Session, dossier_id: int) -> List[Dict[str, Any]]:
    """Get all events for a dossier."""
    dossier = session.get(Dossier, dossier_id)
    if dossier is None:
        return []
    return _build_dossier_events(dossier, _load_timeline_graph(session, [dossier]))


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
            # Déterminer le titre du mouvement
            title = mouv.movement_type or mouv.trigger_event or "Mouvement"
            if mouv.trigger_event and mouv.trigger_event.startswith(mouv.trigger_event.split('^')[0]):
                # Si c'est un code IHE PAM, utiliser une description plus lisible
                event_code = mouv.trigger_event.split('^')[0]
                event_descriptions = {
                    'A01': 'Admission',
                    'A02': 'Transfert',
                    'A03': 'Sortie',
                    'A04': 'Consultation',
                    'A05': 'Pré-admission',
                    'A06': 'Mutation',
                    'A07': 'Retour consultation',
                    'A08': 'Erreur',
                    'A11': 'Annulation admission',
                    'A12': 'Annulation transfert',
                    'A13': 'Annulation sortie',
                    'A21': 'Permission sortie',
                    'A22': 'Retour permission',
                    'A38': 'Annulation pré-admission'
                }
                title = event_descriptions.get(event_code, f"Événement {event_code}")
            
            events.append({
                "type": "mouvement",
                "icon": "activity",
                "color": "orange",
                "title": title,
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
    patient, graph = _load_patient_timeline_graph(session, patient_id)
    if not patient:
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "error.html",
            {"message": "Patient non trouvé"}
        )
    
    events = _build_patient_events(patient, graph)
    
    # Format datetime for display
    for event in events:
        event["datetime_display"] = _format_datetime(event["datetime"])
    
    breadcrumbs = [
        {"label": "Patients", "url": "/patients"},
        {"label": f"{patient.family} {patient.given}", "url": f"/patients/{patient_id}"},
        {"label": "Timeline", "url": f"/timeline/patient/{patient_id}"}
    ]
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "timeline.html",
        {
            "title": f"Timeline - {patient.family} {patient.given}",
            "breadcrumbs": breadcrumbs,
            "events": events,
            "entity_type": "patient",
            "entity_id": patient_id,
            "entity_name": f"{patient.family} {patient.given}",
            "patient": patient,
            "dossiers": graph.dossiers,
            "venues": graph.venues,
            "mouvements": graph.mouvements,
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
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "error.html",
            {"message": "Dossier non trouvé"}
        )
    from app.services.vocabulary_lookup import get_vocabulary_options
    movement_type_options = get_vocabulary_options("movement-nature") or []
    
    graph = _load_timeline_graph(session, [dossier])
    events = _build_dossier_events(dossier, graph)
    
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
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "timeline.html",
        {
            "title": f"Timeline - Dossier #{dossier.dossier_seq}",
            "breadcrumbs": breadcrumbs,
            "events": events,
            "entity_type": "dossier",
            "entity_id": dossier_id,
            "entity_name": f"Dossier #{dossier.dossier_seq}",
            "dossier": dossier,
            "venues": graph.venues,
            "mouvements": graph.mouvements,
            "movement_type_options": movement_type_options
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
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "error.html",
            {"message": "Venue non trouvée"}
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
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "timeline.html",
        {
            "title": f"Timeline - Venue #{venue.venue_seq}",
            "breadcrumbs": breadcrumbs,
            "events": events,
            "entity_type": "venue",
            "entity_id": venue_id,
            "entity_name": f"Venue #{venue.venue_seq}"
        }
    )
