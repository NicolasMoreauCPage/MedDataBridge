from fastapi import APIRouter, Depends, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from datetime import datetime
from typing import Optional
import logging
from app.db import get_session, get_next_sequence, peek_next_sequence
from app.services.vocabulary_lookup import get_vocabulary_options
from app.models import Mouvement, Venue, Dossier
from app.models_structure import UniteFonctionnelle, UniteHebergement, Chambre
from app.services.emit_on_create import emit_to_senders
from app.dependencies.ght import require_ght_context
from app.state_transitions import ALLOWED_TRANSITIONS, INITIAL_EVENTS, SUPPORTED_WORKFLOW_EVENTS

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(
    prefix="/mouvements", 
    tags=["mouvements"],
    dependencies=[Depends(require_ght_context)]
)

def get_status_badge(status):
    colors = {
        'active': 'bg-green-100 text-green-800',
        'completed': 'bg-blue-100 text-blue-800',
        'cancelled': 'bg-red-100 text-red-800',
        'pending': 'bg-yellow-100 text-yellow-800'
    }
    # Guard against None status
    if status is None:
        status = 'inconnu'
    class_name = colors.get(status, 'bg-slate-100 text-slate-800')
    return f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {class_name}">{status.title()}</span>'

def get_type_badge(movement_type: str | None) -> str:
    if not movement_type:
        return '—'
    colors = {
        'admission': 'bg-blue-100 text-blue-800',
        'registration': 'bg-indigo-100 text-indigo-800',
        'preadmission': 'bg-sky-100 text-sky-800',
        'class-change': 'bg-violet-100 text-violet-800',
        'transfer': 'bg-amber-100 text-amber-800',
        'transfer-cancel': 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
        'discharge': 'bg-red-100 text-red-800',
        'discharge-cancel': 'bg-orange-100 text-orange-800',
        'leave-out': 'bg-yellow-100 text-yellow-800',
        'leave-return': 'bg-green-100 text-green-800',
        'doctor-change': 'bg-teal-100 text-teal-800',
        'doctor-change-cancel': 'bg-teal-50 text-teal-700 ring-1 ring-teal-200',
        'update': 'bg-slate-100 text-slate-800',
    }
    label_map = {
        'admission': 'Admission',
        'registration': 'Consultation',
        'preadmission': 'Pré-admission',
        'class-change': 'Mutation',
        'transfer': 'Transfert',
        'transfer-cancel': 'Annul. transfert',
        'discharge': 'Sortie',
        'discharge-cancel': 'Annul. sortie',
        'leave-out': 'Permission',
        'leave-return': 'Retour perm.',
        'doctor-change': 'Change. médecin',
        'doctor-change-cancel': 'Annul. médecin',
        'update': 'MàJ identité',
    }
    class_name = colors.get(movement_type, 'bg-slate-100 text-slate-800')
    label = label_map.get(movement_type, movement_type.title())
    return f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {class_name}">{label}</span>'

@router.get("", response_class=HTMLResponse)
def list_mouvements(
    request: Request,
    venue_id: Optional[int] = Query(None, description="ID de la venue dont on veut voir les mouvements"),
    dossier_id: Optional[int] = Query(None, description="ID du dossier dont on veut voir les mouvements"),
    include_cancelled: bool = Query(False, description="Inclure les mouvements annulés dans la liste"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="Ordre de tri par date"),
    session=Depends(get_session)
):
    venue = None
    dossier = None
    
    # Si venue_id est fourni, on filtre par venue
    if venue_id:
        venue = session.get(Venue, venue_id)
        if not venue:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "title": "Venue introuvable",
                    "message": "La venue spécifiée n'existe pas. Veuillez sélectionner une venue valide.",
                    "back_url": "/dossiers"
                },
                status_code=404
            )
        
        # Charger le contexte complet pour le fil d'Ariane
        session.refresh(venue, ['dossier'])
        if venue.dossier:
            session.refresh(venue.dossier, ['patient'])
            dossier = venue.dossier
        
        # Construction de la requête filtrée par venue
        stmt = select(Mouvement).where(Mouvement.venue_id == venue_id)
        if not include_cancelled:
            stmt = stmt.where((Mouvement.status.is_(None)) | (Mouvement.status != "cancelled"))
        # Tri
        if order == "asc":
            stmt = stmt.order_by(Mouvement.when.asc(), Mouvement.id.asc())
        else:
            stmt = stmt.order_by(Mouvement.when.desc(), Mouvement.id.desc())
    
    # Si dossier_id est fourni (et pas de venue_id), on filtre par dossier
    elif dossier_id:
        # Ensure Dossier refers to the imported model, not a local variable
        dossier = session.get(Dossier, dossier_id)
        if not dossier:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "title": "Dossier introuvable",
                    "message": "Le dossier spécifié n'existe pas. Veuillez sélectionner un dossier valide.",
                    "back_url": "/dossiers"
                },
                status_code=404
            )
        
        # Charger le patient pour le fil d'Ariane
        session.refresh(dossier, ['patient'])
        
        # Construction de la requête filtrée par dossier (via les venues)
        stmt = select(Mouvement).join(Venue).where(Venue.dossier_id == dossier_id)
        if not include_cancelled:
            stmt = stmt.where((Mouvement.status.is_(None)) | (Mouvement.status != "cancelled"))
        # Tri
        if order == "asc":
            stmt = stmt.order_by(Mouvement.when.asc(), Mouvement.id.asc())
        else:
            stmt = stmt.order_by(Mouvement.when.desc(), Mouvement.id.desc())
    
    # Sinon, filtrer par contexte EJ si présent
    else:
        ej_context = getattr(request.state, "ej_context", None)
        if ej_context and getattr(ej_context, "id", None):
            # Récupérer tous les dossiers de l'EJ
            from app.models import Dossier
            dossier_ids = [d.id for d in session.exec(select(Dossier).where(Dossier.entite_juridique_id == ej_context.id))]
            if dossier_ids:
                venue_ids = [v.id for v in session.exec(select(Venue).where(Venue.dossier_id.in_(dossier_ids)))]
                if venue_ids:
                    stmt = select(Mouvement).where(Mouvement.venue_id.in_(venue_ids))
                    # Optionally filter out cancelled
                    if not include_cancelled:
                        stmt = stmt.where((Mouvement.status.is_(None)) | (Mouvement.status != "cancelled"))
                    # Tri
                    if order == "asc":
                        stmt = stmt.order_by(Mouvement.when.asc(), Mouvement.id.asc())
                    else:
                        stmt = stmt.order_by(Mouvement.when.desc(), Mouvement.id.desc())
                    mouvements = session.exec(stmt).all()
                else:
                    mouvements = []
            else:
                mouvements = []
        else:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "title": "Paramètre manquant",
                    "message": "Vous devez spécifier soit un dossier_id soit un venue_id pour voir les mouvements.",
                    "back_url": "/dossiers"
                },
                status_code=400
            )
    # Exécuter la requête si pas déjà fait
    if 'mouvements' not in locals():
        mouvements = session.exec(stmt).all()

    # Préparer les lignes avec les actions détaillées
    def _type_cell(m: Mouvement) -> str:
        badge = get_type_badge(getattr(m, 'movement_type', None))
        seq_note = ""
        if getattr(m, 'cancelled_movement_seq', None):
            seq_note = f"<span class='ml-2 text-xs text-slate-500'>(annule #{m.cancelled_movement_seq})</span>"
        return badge + seq_note

    rows = [
        {
            "cells": [
                m.mouvement_seq,
                m.id,
                m.venue_id,
                _type_cell(m),
                get_status_badge(getattr(m, 'status', 'pending')),
                m.when.strftime("%d/%m/%Y %H:%M") if m.when else None,
                m.location,
                m.performer,
            ],
            "detail_url": f"/mouvements/{m.id}",
            "edit_url": f"/mouvements/{m.id}/edit",
            "delete_url": f"/mouvements/{m.id}/delete",
        }
        for m in mouvements
    ]

    # Construire le fil d'Ariane
    breadcrumbs = [{"label": "Mouvements", "url": "#"}]
    
    if venue_id and venue:
        # Cas 1 : Filtrage par venue spécifique
        breadcrumbs.insert(0, {"label": f"Venue #{venue.venue_seq}", "url": f"/venues/{venue_id}"})
        if venue.dossier:
            breadcrumbs.insert(0, {"label": f"Dossier #{venue.dossier.dossier_seq}", "url": f"/dossiers/{venue.dossier.id}"})
            if venue.dossier.patient:
                breadcrumbs.insert(0, {
                    "label": f"Patient: {venue.dossier.patient.family} {venue.dossier.patient.given}",
                    "url": f"/patients/{venue.dossier.patient.id}"
                })
    elif dossier_id and dossier:
        # Cas 2 : Filtrage par dossier (tous les mouvements du dossier)
        breadcrumbs.insert(0, {"label": f"Dossier #{dossier.dossier_seq}", "url": f"/dossiers/{dossier.id}"})
        if dossier.patient:
            breadcrumbs.insert(0, {
                "label": f"Patient: {dossier.patient.family} {dossier.patient.given}",
                "url": f"/patients/{dossier.patient.id}"
            })

    # Définir les filtres de recherche
    filters = [
        {
            "label": "Type",
            "name": "type",
            "type": "select",
            "placeholder": "Tous les types",
            "options": [
                {"value": "ADT^A01", "label": "Admission"},
                {"value": "ADT^A02", "label": "Transfert"},
                {"value": "ADT^A03", "label": "Sortie"},
                {"value": "ADT^A04", "label": "Urgences / consultation externe"}
            ]
        },
        {
            "label": "Statut",
            "name": "status",
            "type": "select",
            "placeholder": "Tous les statuts",
            "options": [
                {"value": "pending", "label": "En attente"},
                {"value": "active", "label": "En cours"},
                {"value": "completed", "label": "Terminé"},
                {"value": "cancelled", "label": "Annulé"}
            ]
        },
        {
            "label": "Localisation",
            "name": "location",
            "type": "text",
            "placeholder": "Filtrer par localisation"
        }
    ]

    # Définir les actions disponibles
    # Ajouter une action pour inclure/masquer les annulés
    toggle_cancel_url = None
    context_query = f"venue_id={venue_id}" if venue_id else (f"dossier_id={dossier_id}" if dossier_id else "")
    if context_query:
        if include_cancelled:
            toggle_cancel_url = f"/mouvements?{context_query}&include_cancelled=0&order={order}"
        else:
            toggle_cancel_url = f"/mouvements?{context_query}&include_cancelled=1&order={order}"

    actions = [
        # Vues explicites
        ({
            "type": "link",
            "label": "Vue état actuel",
            "url": f"/mouvements/etat?{context_query}" if context_query else "/mouvements/etat"
        } if context_query else None),
        ({
            "type": "link",
            "label": "Vue historique",
            "url": f"/mouvements/historique?{context_query}" if context_query else "/mouvements/historique"
        } if context_query else None),
        {
            "type": "link",
            "label": "Export FHIR",
            "url": "/mouvements/export/fhir"
        },
        {
            "type": "link",
            "label": "Export HL7",
            "url": "/mouvements/export/hl7"
        }
    ]

    # Nettoyer actions None
    actions = [a for a in actions if a]

    if toggle_cancel_url:
        actions.insert(0, {
            "type": "link",
            "label": ("Masquer les annulés" if include_cancelled else "Afficher les annulés"),
            "url": toggle_cancel_url
        })

    # Toggle tri
    if context_query:
        if order == "asc":
            toggle_order_url = f"/mouvements?{context_query}&include_cancelled={'1' if include_cancelled else '0'}&order=desc"
            actions.insert(0, {"type": "link", "label": "Trier: plus récent → plus ancien", "url": toggle_order_url})
        else:
            toggle_order_url = f"/mouvements?{context_query}&include_cancelled={'1' if include_cancelled else '0'}&order=asc"
            actions.insert(0, {"type": "link", "label": "Trier: plus ancien → plus récent", "url": toggle_order_url})

    # Construire le contexte complet
    if venue_id and venue:
        base = f"de la venue #{venue.venue_seq}"
    elif dossier_id and dossier:
        base = f"du dossier #{dossier.dossier_seq}"
    else:
        base = ""

    if include_cancelled:
        title = f"Historique des mouvements {base}".strip()
    else:
        title = f"Mouvements (état actuel) {base}".strip()
    
    # Tabs ergonomiques pour basculer entre vues
    tabs = None
    if context_query:
        tabs = [
            {
                "label": "État actuel",
                "url": f"/mouvements/etat?{context_query}",
                "active": not include_cancelled,
            },
            {
                "label": "Historique",
                "url": f"/mouvements/historique?{context_query}",
                "active": include_cancelled,
            },
        ]

    ctx = {
        "request": request,
        "title": title,
        "breadcrumbs": breadcrumbs,
        "tabs": tabs,
        "headers": ["Seq", "ID", "Venue", "Type", "Status", "Date/Heure", "Localisation", "Intervenant"],
        "rows": rows,
    "context": {"venue_id": venue_id, "include_cancelled": include_cancelled, "order": order},
    "new_url": f"/mouvements/new?venue_id={venue_id}" if venue_id else (f"/mouvements/new?dossier_id={dossier_id}" if dossier_id else "/mouvements/new"),
        "filters": filters,
        "actions": actions,
        "show_actions": True
    }

    return templates.TemplateResponse(request, "list.html", ctx)


@router.get("/historique")
def mouvements_historique(
    request: Request,
    venue_id: Optional[int] = Query(None),
    dossier_id: Optional[int] = Query(None),
):
    """Redirige vers la liste en mode historique (inclut les annulés)."""
    if venue_id:
        return RedirectResponse(f"/mouvements?venue_id={venue_id}&include_cancelled=1", status_code=303)
    if dossier_id:
        return RedirectResponse(f"/mouvements?dossier_id={dossier_id}&include_cancelled=1", status_code=303)
    return RedirectResponse("/mouvements?include_cancelled=1", status_code=303)


@router.get("/etat")
def mouvements_etat(
    request: Request,
    dossier_id: Optional[int] = Query(None, description="ID du dossier concerné"),
    venue_id: Optional[int] = Query(None, description="ID de la venue concernée"),
):
    """Redirige vers la liste 'état actuel' (sans annulés)."""
    if dossier_id:
        return RedirectResponse(f"/mouvements?dossier_id={dossier_id}&include_cancelled=0", status_code=303)
    if venue_id:
        return RedirectResponse(f"/mouvements?venue_id={venue_id}&include_cancelled=0", status_code=303)
    return RedirectResponse("/mouvements", status_code=303)

@router.get("/new", response_class=HTMLResponse)
def new_mouvement(
    request: Request,
    venue_id: int | None = Query(None, description="ID de la venue pour laquelle créer un mouvement (pré-rempli si fourni)"),
    dossier_id: int | None = Query(None, description="ID du dossier pour filtrer les venues disponibles"),
    session=Depends(get_session)
):
    from app.form_config import MovementType, MouvementStatus
    from app.models import Dossier
    
    # Déterminer le dossier de filtrage
    filter_dossier_id = dossier_id
    if filter_dossier_id is None and hasattr(request.state, 'dossier_context') and request.state.dossier_context:
        filter_dossier_id = request.state.dossier_context.id
    
    # Récupérer les venues disponibles (filtrées par dossier si fourni)
    if filter_dossier_id:
        stmt = select(Venue).where(Venue.dossier_id == filter_dossier_id).order_by(Venue.venue_seq.asc())
    else:
        # Filtrer les venues qui ont un dossier avec une EJ valide
        from app.models import Dossier
        stmt = select(Venue).join(Dossier).where(Dossier.entite_juridique_id.is_not(None)).order_by(Venue.venue_seq.asc())
    
    venues = session.exec(stmt).all()
    
    # Si une venue spécifique est demandée mais n'est pas dans la liste (à cause de la limit), l'ajouter
    if venue_id and not any(v.id == venue_id for v in venues):
        requested_venue = session.get(Venue, venue_id)
        if requested_venue:
            # Vérifier qu'elle satisfait les critères (dossier avec EJ si pas de filter_dossier_id)
            if filter_dossier_id:
                if requested_venue.dossier_id == filter_dossier_id:
                    venues.append(requested_venue)
            else:
                if requested_venue.dossier and requested_venue.dossier.entite_juridique_id:
                    venues.append(requested_venue)
    
    if not venues:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": "Aucune venue disponible",
                "message": "Impossible de créer un mouvement : aucune venue n'est disponible. Créez d'abord une venue.",
                "back_url": "/venues/new" if filter_dossier_id else "/dossiers"
            },
            status_code=404
        )
    

    # --- Automatisation des pré-remplissages et restrictions ---
    # Pré-remplir venue
    prefill_venue_id = venue_id
    if prefill_venue_id is None and hasattr(request.state, 'venue_context') and request.state.venue_context:
        prefill_venue_id = request.state.venue_context.id
    if prefill_venue_id is None:
        prefill_venue_id = venues[0].id

    next_seq = peek_next_sequence(session, "mouvement")

    # Récupérer la venue sélectionnée
    selected_venue = session.get(Venue, prefill_venue_id)
    logging.info(f"prefill_venue_id: {prefill_venue_id}")
    logging.info(f"selected_venue: {selected_venue}")
    if selected_venue:
        logging.info(f"selected_venue.uf_responsabilite: {selected_venue.uf_responsabilite}")
    selected_dossier = selected_venue.dossier if selected_venue else None
    selected_uf_id = None
    selected_uh_id = None
    selected_uf_soins_id = None
    selected_chambre_id = None
    selected_lit_id = None
    prefill_from_location = None
    prefill_to_location = None
    prefill_reason = None
    prefill_movement_reason = None

    # Pré-remplir les champs depuis le dernier mouvement si il existe
    last_movement = None
    if prefill_venue_id:
        movements = session.exec(
            select(Mouvement)
            .where(Mouvement.venue_id == prefill_venue_id)
            .order_by(Mouvement.when.desc())
        ).all()
        if movements:
            last_movement = movements[0]  # Le plus récent (desc)
            logging.info(f"Found last movement {last_movement.id} for venue {prefill_venue_id}")

            # Pré-remplir UF médicale depuis le dernier mouvement
            if last_movement.uf_responsabilite:
                uf_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == last_movement.uf_responsabilite)).first()
                if uf_obj:
                    selected_uf_id = uf_obj.id
                    logging.info(f"Pre-filled UF from last movement: {uf_obj.name} (ID: {uf_obj.id})")

            # Pré-remplir UF soins depuis le dernier mouvement
            if last_movement.uf_soins_code:
                uf_soins_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == last_movement.uf_soins_code)).first()
                if uf_soins_obj:
                    selected_uf_soins_id = uf_soins_obj.identifier
                    logging.info(f"Pre-filled UF soins from last movement: {uf_soins_obj.name} (ID: {uf_soins_obj.identifier})")

            # Pré-remplir UH depuis le dernier mouvement
            if last_movement.location:
                # Essayer de parser l'UF depuis la location (format: UF-UFIDENT-CHAMBRE-LIT)
                location_parts = last_movement.location.split('-')
                if len(location_parts) >= 1:
                    uf_part = location_parts[0]
                    if uf_part.startswith('UF'):
                        uh_part = location_parts[1] if len(location_parts) > 1 else None
                        if uh_part:
                            uh_obj = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == uh_part)).first()
                            if uh_obj:
                                selected_uh_id = uh_obj.id
                                logging.info(f"Pre-filled UH from last movement: {uh_obj.name} (ID: {uh_obj.id})")

            # Pré-remplir chambre depuis le dernier mouvement
            if last_movement.location:
                location_parts = last_movement.location.split('-')
                if len(location_parts) >= 3:
                    chambre_part = location_parts[2]
                    chambre_obj = session.exec(select(Chambre).where(Chambre.identifier == chambre_part)).first()
                    if chambre_obj:
                        selected_chambre_id = chambre_obj.id
                        logging.info(f"Pre-filled chambre from last movement: {chambre_obj.name} (ID: {chambre_obj.id})")

            # Pré-remplir lit depuis le dernier mouvement
            if last_movement.location:
                location_parts = last_movement.location.split('-')
                if len(location_parts) >= 4:
                    lit_part = location_parts[3]
                    # Pour le lit, on utilise l'ID de la chambre comme approximation
                    if selected_chambre_id:
                        selected_lit_id = selected_chambre_id
                        logging.info(f"Pre-filled lit from last movement: chambre {selected_chambre_id}")

            # Pré-remplir autres champs depuis le dernier mouvement
            prefill_from_location = last_movement.from_location
            prefill_to_location = last_movement.to_location
            prefill_reason = last_movement.reason
            prefill_movement_reason = last_movement.movement_reason
        else:
            logging.info(f"No previous movements found for venue {prefill_venue_id}, using venue defaults")
            # Pas de mouvement précédent, utiliser les valeurs par défaut de la venue
            # Pré-remplir UF depuis la venue ou le dossier (logique existante)
            if selected_venue and selected_venue.uf_responsabilite:
                logging.info(f"Selected venue {selected_venue.id} has uf_responsabilite: {selected_venue.uf_responsabilite}")
                # Si venue a une UF, chercher son id
                uf_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == selected_venue.uf_responsabilite)).first()
                if uf_obj:
                    selected_uf_id = uf_obj.id
                    logging.info(f"Found UF {uf_obj.name} (ID: {uf_obj.id}) for venue")
                else:
                    logging.warning(f"UF not found for identifier {selected_venue.uf_responsabilite}")
            elif selected_dossier and selected_dossier.uf_responsabilite and selected_dossier.uf_responsabilite.strip():
                logging.info(f"Selected dossier {selected_dossier.id} has uf_responsabilite: {selected_dossier.uf_responsabilite}")
                uf_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == selected_dossier.uf_responsabilite)).first()
                if uf_obj:
                    selected_uf_id = uf_obj.id
                    logging.info(f"Found UF {uf_obj.name} (ID: {uf_obj.id}) for dossier")
                else:
                    logging.warning(f"UF not found for identifier {selected_dossier.uf_responsabilite}")

            # Pré-remplir UH si UF connue
            if selected_uf_id:
                logging.info(f"Looking for UH for UF {selected_uf_id}")
                uh_obj = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == selected_uf_id)).first()
                if uh_obj:
                    selected_uh_id = uh_obj.id
                    logging.info(f"Found UH {uh_obj.name} (ID: {uh_obj.id}) for UF")
                else:
                    logging.warning(f"No UH found for UF {selected_uf_id}")
    else:
        # Pas de venue pré-remplie
        pass

    # Déterminer le dernier événement et la date par défaut
    allowed_events_codes = None
    default_when_str = None
    try:
        if prefill_venue_id:
            last = session.exec(
                select(Mouvement)
                .where(Mouvement.venue_id == prefill_venue_id)
                .order_by(Mouvement.when)
            ).all()
            if last:
                last_event = last[-1].type.split('^')[-1] if last[-1].type else None
                allowed_events_codes = ALLOWED_TRANSITIONS.get(last_event, set())
                from datetime import timedelta
                default_when_str = (last[-1].when + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
            else:
                allowed_events_codes = {e for e in INITIAL_EVENTS if e != "A38"}
                default_when_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
        else:
            default_when_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
    except Exception:
        allowed_events_codes = None
        default_when_str = datetime.now().strftime("%Y-%m-%dT%H:%M")

    # Préparer la liste déroulante des venues
    venue_options = []
    for v in venues:
        session.refresh(v, ['dossier'])
        label = f"Venue #{v.venue_seq}"
        if v.dossier:
            session.refresh(v.dossier, ['patient'])
            if v.dossier.patient:
                label += f" - {v.dossier.patient.family} {v.dossier.patient.given}"
            label += f" (Dossier #{v.dossier.dossier_seq})"
        venue_options.append({"value": str(v.id), "label": label})

    # Récupérer l'UF de responsabilité médicale et les UF d'hébergement liées à la venue
        uf_options = []
        try:
            from app.models_structure import UniteFonctionnelle, UniteHebergement
            uf_ids = set()

            # Récupérer l'EJ de la venue sélectionnée pour filtrer les UF
            ej_id = None
            if selected_venue and selected_venue.dossier:
                ej_id = selected_venue.dossier.entite_juridique_id

            # UF de responsabilité médicale
            if selected_venue and selected_venue.uf_responsabilite and selected_venue.uf_responsabilite.strip():
                uf_med = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == selected_venue.uf_responsabilite)).first()
                if uf_med:
                    uf_ids.add(uf_med.id)

            # UF d'hébergement via UH de la venue
            if selected_venue:
                uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id.is_not(None))).all()
                for uh in uhs:
                    if hasattr(uh, 'venue_id') and uh.venue_id == selected_venue.id:
                        uf_heberg = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.id == uh.unite_fonctionnelle_id)).first()
                        if uf_heberg:
                            uf_ids.add(uf_heberg.id)

            # Toujours ajouter les UF de l'EJ de la venue (même si on a trouvé des UF spécifiques)
            if ej_id:
                # Récupérer toutes les UF de l'EJ via la hiérarchie EG -> Pole -> Service -> UF
                from app.models_structure_fhir import EntiteGeographique
                from app.models_structure import Pole, Service

                # EJ -> Entites Geographiques
                entites_geo = session.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej_id)).all()

                for eg in entites_geo:
                    # EG -> Poles
                    poles = session.exec(select(Pole).where(Pole.entite_geo_id == eg.id)).all()

                    for pole in poles:
                        # Pole -> Services
                        services = session.exec(select(Service).where(Service.pole_id == pole.id)).all()

                        for service in services:
                            # Service -> UF
                            service_ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id)).all()
                            uf_ids.update(uf.id for uf in service_ufs)

            # Fallback: si toujours aucune UF, utiliser toutes les UF (pour compatibilité)
            if not uf_ids:
                all_ufs = session.exec(select(UniteFonctionnelle).order_by(UniteFonctionnelle.name)).all()
                uf_ids.update(uf.id for uf in all_ufs)
            
            # Récupérer les objets UF et créer les options
            ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.id.in_(uf_ids))).all()

            for uf in ufs:
                label = uf.short_name if getattr(uf, 'short_name', None) and uf.short_name and uf.short_name.strip() else uf.name
                uf_options.append({"value": uf.identifier, "label": label})
        except Exception as e:
            uf_options = []

    # Récupérer les UH pour l'UF pré-remplie
    uh_options = []
    if selected_uf_id:
        logging.info(f"Getting UH options for UF {selected_uf_id}")
        uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == selected_uf_id)).all()
        logging.info(f"Found {len(uhs)} UH for UF {selected_uf_id}")
        for uh in uhs:
            label = f"{uh.identifier} — {uh.name}"
            uh_options.append({"value": str(uh.id), "label": label})
    else:
        logging.info("No selected_uf_id, using fallback UH options")
        # Fallback: utiliser toutes les UH disponibles
        uhs = session.exec(select(UniteHebergement).order_by(UniteHebergement.name)).all()
        logging.info(f"Found {len(uhs)} UH in fallback")
        for uh in uhs:
            label = f"{uh.identifier} — {uh.name}"
            uh_options.append({"value": str(uh.id), "label": label})
    

    # Filtrer les types de mouvement selon le type de venue
    from app.form_config import MovementType
    from app.movement_type_mapping import from_standard_movement_code, to_standard_movement_code
    all_type_options = MovementType.choices()
    # Mapping dossier_type -> types autorisés (codes HL7)
    type_map = {
        "hospitalise": ["ADT^A01", "ADT^A02", "ADT^A03", "ADT^A06", "ADT^A11", "ADT^A12", "ADT^A13", "ADT^A21"],
        "externe": ["ADT^A04", "ADT^A07"],
        "urgence": ["ADT^A04", "ADT^A05", "ADT^A07", "ADT^A21"],
    }
    allowed_types = None
    if selected_dossier:
        dt = selected_dossier.dossier_type.value if hasattr(selected_dossier.dossier_type, 'value') else str(selected_dossier.dossier_type)
        hl7_codes = type_map.get(dt, None)
        if hl7_codes:
            # Convertir les codes HL7 en types métier
            allowed_types = [from_standard_movement_code(code, "hl7") for code in hl7_codes if from_standard_movement_code(code, "hl7")]
    def _opt_allowed(opt):
        try:
            metier_code = str(opt.get("value"))
            # Convertir le type métier en code HL7 pour vérifier allowed_events_codes
            hl7_code = to_standard_movement_code(metier_code, "hl7")
            if hl7_code:
                event = hl7_code.split("^")[-1]
                if allowed_events_codes and event not in allowed_events_codes:
                    return False
            if allowed_types and metier_code not in allowed_types:
                return False
            return True
        except Exception:
            return True
    filtered = [opt for opt in all_type_options if _opt_allowed(opt)]

    # Ajouter un indicateur requires_location aux options
    event_mapping = {
        "A01": ("admission", True),
        "A02": ("transfer", True),
        "A03": ("discharge", False),
        "A04": ("consultation_out", False),
        "A05": ("preadmission", False),
        "A06": ("class_change", True),
        "A07": ("from_consult", True),
        "A11": ("cancel_admission", False),
        "A12": ("cancel_transfer", False),
        "A13": ("cancel_discharge", False),
        "A21": ("temporary_leave", False),
        "A22": ("return", True),
        "A38": ("cancel_preadmission", False),
    }
    type_options = []
    for opt in filtered:
        if isinstance(opt, dict):
            code = str(opt.get("value", ""))
            evt = code.split("^")[-1] if "^" in code else code
            requires = bool(event_mapping.get(evt, (None, False))[1])
            enriched = {**opt, "requires_location": requires}
            type_options.append(enriched)
        else:
            type_options.append(opt)

    # Motif/raison en dropdownlist vocabulaire
    from app.services.vocabulary_lookup import get_vocabulary_options
    reason_options = get_vocabulary_options("movement-reason")

    fields = [
        {
            "label": "Venue (Séjour) *",
            "name": "venue_id",
            "type": "select",
            "options": venue_options,
            "value": str(prefill_venue_id),
            "required": True,
            "help": "Sélectionnez la venue concernée par ce mouvement"
        },
        {
            "label": "Type de mouvement *",
            "name": "type",
            "type": "select",
            "options": type_options,
            "required": True,
            "help": "Options filtrées selon l'état actuel de la venue et le type de séjour"
        },
        {
            "label": "Date et heure *",
            "name": "when",
            "type": "datetime-local",
            "value": default_when_str,
            "required": True,
            "help": "Date et heure du mouvement"
        },
        {
            "label": "Unité médicale (UF)",
            "name": "uf_id",
            "type": "select",
            "options": uf_options,
            "value": selected_venue.uf_responsabilite if (selected_venue and selected_venue.uf_responsabilite and not last_movement) else (selected_uf_id if selected_uf_id else None),
            "help": "Sélectionnez l'UF médicale concernée (pré-remplie depuis le dernier mouvement ou la venue)"
        },
        {
            "label": "Unité de Soins (UF Soins)",
            "name": "uf_soins_id",
            "type": "select",
            "options": uf_options,  # Même options que l'UF principale
            "value": selected_uf_soins_id,
            "help": "Sélectionnez l'unité de soins (pré-remplie depuis le dernier mouvement)"
        },
        {
            "label": "Unité d'Hébergement (UH)",
            "name": "uh_id",
            "type": "select",
            "options": uh_options,
            "value": str(selected_uh_id) if selected_uh_id else None,
            "help": "Sélectionnez l'unité d'hébergement liée à l'UF (pré-remplie depuis le dernier mouvement)"
        },
        {
            "label": "Chambre",
            "name": "chambre_id",
            "type": "select",
            "options": chambre_options,
            "value": str(selected_chambre_id) if selected_chambre_id else None,
            "help": "Sélectionnez la chambre (pré-remplie depuis le dernier mouvement)",
            "depends_on": "uh_id"
        },
        {
            "label": "Lit",
            "name": "lit_id",
            "type": "select",
            "options": lit_options,
            "value": str(selected_lit_id) if selected_lit_id else None,
            "help": "Sélectionnez le lit (pré-rempli depuis le dernier mouvement)",
            "depends_on": "chambre_id"
        },
        {
            "label": "Depuis (départ)",
            "name": "from_location",
            "type": "text",
            "value": prefill_from_location,
            "help": "Pour les transferts : lieu de départ (pré-rempli depuis le dernier mouvement)"
        },
        {
            "label": "Vers (arrivée)",
            "name": "to_location",
            "type": "text",
            "value": prefill_to_location,
            "help": "Pour les transferts : lieu d'arrivée (pré-rempli depuis le dernier mouvement)"
        },
        {
            "label": "Raison / Motif",
            "name": "reason",
            "type": "select" if reason_options else "text",
            "options": reason_options,
            "value": prefill_reason,
            "help": "Motif du mouvement (pré-rempli depuis le dernier mouvement)"
        },
        {
            "label": "Numéro de séquence",
            "name": "mouvement_seq",
            "type": "number",
            "value": next_seq,
            "readonly": True,
            "help": "Généré automatiquement - ne modifier que si nécessaire"
        },
        {
            "label": "Statut du mouvement",
            "name": "status",
            "type": "select",
            "options": MouvementStatus.choices(),
            "value": "pending",
            "readonly": True,
            "hidden": True,
            "help": "Indicateur interne, non modifiable."
        },
    ]

    back_url = f"/mouvements?dossier_id={filter_dossier_id}" if filter_dossier_id else "/venues"
    title = "Nouveau mouvement"
    if filter_dossier_id:
        dossier = session.get(Dossier, filter_dossier_id)
        if dossier:
            title += f" pour le dossier #{dossier.dossier_seq}"

    return templates.TemplateResponse(
        request,
        "form.html",
        {
            "title": title,
            "fields": fields,
            "back_url": back_url
        }
    )


@router.post("/new")
def create_mouvement(
    request: Request,
    venue_id: int = Form(...),
    type: str = Form(...),
    when: str = Form(...),
    uf_id: int = Form(None),
    uf_soins_id: str = Form(None),
    uh_id: int = Form(None),
    chambre_id: int = Form(None),
    lit_id: int = Form(None),
    from_location: str = Form(None),
    to_location: str = Form(None),
    reason: str = Form(None),
    mouvement_seq: int | None = Form(None),
    movement_reason: str = Form(None),
    session=Depends(get_session),
):
    # Parse date/time
    when_dt = datetime.fromisoformat(when)
    
    # Validation: prevent retroactive movements (before venue start_time or last movement)
    venue = session.get(Venue, venue_id)
    if venue:
        # Check against venue start_time
        if venue.start_time and when_dt < venue.start_time:
            raise HTTPException(
                status_code=400,
                detail=f"La date du mouvement ({when_dt.strftime('%d/%m/%Y %H:%M')}) ne peut pas être antérieure au début de la venue ({venue.start_time.strftime('%d/%m/%Y %H:%M')})"
            )
        
        # Check against last movement's when
        last_movements = session.exec(
            select(Mouvement)
            .where(Mouvement.venue_id == venue_id)
            .order_by(Mouvement.when.desc())
        ).all()
        if last_movements and last_movements[0].when:
            if when_dt < last_movements[0].when:
                raise HTTPException(
                    status_code=400,
                    detail=f"La date du mouvement ({when_dt.strftime('%d/%m/%Y %H:%M')}) ne peut pas être antérieure au dernier mouvement ({last_movements[0].when.strftime('%d/%m/%Y %H:%M')})"
                )
    
    # Determine event code (A01, A02, ...)
    trigger_event = None
    if type:
        parts = type.split("^", 1)
        if len(parts) == 2:
            trigger_event = parts[1]

    # Server-side validation: ensure transition is allowed from current state
    if venue_id and trigger_event:
        last = session.exec(
            select(Mouvement)
            .where(Mouvement.venue_id == venue_id)
            .order_by(Mouvement.when)
        ).all()
        last_event = last[-1].type.split('^')[-1] if last else None
        allowed = (ALLOWED_TRANSITIONS.get(last_event, set()) if last_event else {e for e in INITIAL_EVENTS if e != "A38"})
        if trigger_event not in allowed:
            raise HTTPException(status_code=400, detail=f"L'événement {trigger_event} n'est pas autorisé dans l'état actuel")

    # Map movement_type for downstream systems (align with workflow router)
    event_mapping = {
        "A01": ("admission", True),
        "A02": ("transfer", True),
        "A03": ("discharge", False),
        "A04": ("consultation_out", False),
        "A05": ("preadmission", False),
        "A06": ("class_change", True),
        "A07": ("from_consult", True),
        "A11": ("cancel_admission", False),
        "A12": ("cancel_transfer", False),
        "A13": ("cancel_discharge", False),
        "A21": ("temporary_leave", False),
        "A22": ("return", True),
        "A38": ("cancel_preadmission", False),
    }

    # Enforce location requirement according to mapping (kept consistent with workflow router)
    requires_location = bool(event_mapping.get(trigger_event, (None, False))[1])
    if requires_location and not (uh_id or chambre_id):
        raise HTTPException(status_code=400, detail="La localisation est obligatoire pour ce type de mouvement")

    # Sequence generation (always generate new, ignore form value)
    seq = get_next_sequence(session, "mouvement")
    mapped_movement_type = None
    if trigger_event in event_mapping:
        mapped_movement_type = event_mapping[trigger_event][0]
    
    # Récupérer les informations de l'UF de soins si fournie
    uf_soins_code = None
    uf_soins_label = None
    if uf_soins_id:
        from app.models_structure import UniteFonctionnelle
        uf_soins_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == uf_soins_id)).first()
        if uf_soins_obj:
            uf_soins_code = uf_soins_obj.identifier
            uf_soins_label = uf_soins_obj.short_name if getattr(uf_soins_obj, 'short_name', None) and uf_soins_obj.short_name and uf_soins_obj.short_name.strip() else uf_soins_obj.name
    
    # Récupérer les informations de l'UF responsable si fournie
    uf_responsabilite = None
    if uf_id:
        from app.models_structure import UniteFonctionnelle
        uf_resp_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.id == uf_id)).first()
        if uf_resp_obj:
            uf_responsabilite = uf_resp_obj.identifier
    
    m = Mouvement(
        venue_id=venue_id,
        type=type,
        when=when_dt,
        from_location=from_location,
        to_location=to_location,
        reason=reason,
        mouvement_seq=seq,
        movement_type=mapped_movement_type,
        movement_reason=movement_reason,
        trigger_event=trigger_event,
        uf_responsabilite=uf_responsabilite,
        uf_soins_code=uf_soins_code,
        uf_soins_label=uf_soins_label,
    )
    session.add(m)
    session.commit()
    emit_to_senders(m, "mouvement", session)
    return RedirectResponse(url=f"/mouvements?venue_id={venue_id}", status_code=303)

@router.get("/{mouvement_id}", response_class=HTMLResponse)
def mouvement_detail(mouvement_id: int, request: Request, session=Depends(get_session)):
    require_ght_context(request)
    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)
    
    # Récupérer les informations enrichies pour l'affichage
    from app.models_structure import UniteFonctionnelle, UniteHebergement, Chambre
    
    # UF Responsable
    uf_responsable_label = None
    if m.uf_responsabilite:
        uf_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == m.uf_responsabilite)).first()
        if uf_obj:
            uf_responsable_label = uf_obj.short_name if getattr(uf_obj, 'short_name', None) and uf_obj.short_name and uf_obj.short_name.strip() else uf_obj.name
    
    # UF Soins
    uf_soins_label = m.uf_soins_label
    if not uf_soins_label and m.uf_soins_code:
        uf_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == m.uf_soins_code)).first()
        if uf_obj:
            uf_soins_label = uf_obj.short_name if getattr(uf_obj, 'short_name', None) and uf_obj.short_name and uf_obj.short_name.strip() else uf_obj.name
    
    # UF Hébergement depuis la location (différents formats possibles)
    uf_hebergement_label = None
    chambre_info = None
    lit_info = None
    if m.location:
        location_str = str(m.location).strip()
        
        # Format 1: "UH-identifier^chambre-identifier" (ex: "UH-696915001750^6969150017507011")
        if '^' in location_str:
            parts = location_str.split('^', 1)
            uh_part = parts[0].strip()
            chambre_part = parts[1].strip() if len(parts) > 1 else ""
            
            # Extraire l'identifier UH (peut être "UH-ident" ou juste "ident")
            uh_identifier = uh_part
            if not uh_part.startswith('UH-'):
                uh_identifier = f'UH-{uh_part}'  # Ajouter le préfixe si manquant
            
            uh_obj = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == uh_identifier)).first()
            if uh_obj and uh_obj.unite_fonctionnelle:
                uf_hebergement_label = uh_obj.unite_fonctionnelle.short_name if getattr(uh_obj.unite_fonctionnelle, 'short_name', None) and uh_obj.unite_fonctionnelle.short_name and uh_obj.unite_fonctionnelle.short_name.strip() else uh_obj.unite_fonctionnelle.name
            
            # Chambre
            if chambre_part:
                chambre_obj = session.exec(select(Chambre).where(Chambre.identifier == chambre_part)).first()
                if chambre_obj:
                    chambre_info = chambre_obj.name if chambre_obj.name else chambre_obj.identifier
        
        # Format 2: Format avec tirets "UF-UFIDENT-CHAMBRE-LIT" (ancien format)
        elif '-' in location_str and len(location_str.split('-')) >= 3:
            location_parts = location_str.split('-')
            if len(location_parts) >= 3:
                chambre_identifier = location_parts[2]
                chambre_obj = session.exec(select(Chambre).where(Chambre.identifier == chambre_identifier)).first()
                if chambre_obj:
                    chambre_info = chambre_obj.name if chambre_obj.name else chambre_obj.identifier
                    if len(location_parts) >= 4:
                        lit_identifier = location_parts[3]
                        lit_info = f"Lit {lit_identifier}"
        
        # Format 3: Référence directe à une chambre
        else:
            # Essayer de trouver directement comme chambre
            chambre_obj = session.exec(select(Chambre).where(Chambre.identifier == location_str)).first()
            if chambre_obj:
                chambre_info = chambre_obj.name if chambre_obj.name else chambre_obj.identifier
                # Si la chambre a une UH, récupérer l'UF
                if chambre_obj.unite_hebergement and chambre_obj.unite_hebergement.unite_fonctionnelle:
                    uf_hebergement_label = chambre_obj.unite_hebergement.unite_fonctionnelle.short_name if getattr(chambre_obj.unite_hebergement.unite_fonctionnelle, 'short_name', None) and chambre_obj.unite_hebergement.unite_fonctionnelle.short_name and chambre_obj.unite_hebergement.unite_fonctionnelle.short_name.strip() else chambre_obj.unite_hebergement.unite_fonctionnelle.name
    
    # Type avec libellé
    type_badge = get_type_badge(getattr(m, 'movement_type', None))
    status_badge = get_status_badge(getattr(m, 'status', 'pending'))
    from app.services.vocabulary_lookup import get_vocabulary_options
    movement_type_options = get_vocabulary_options("movement-nature") or []
    
    # Déterminer le libellé du type
    type_label = None
    if m.movement_type and movement_type_options:
        for opt in movement_type_options:
            if opt.get('value') == m.movement_type:
                type_label = opt.get('label')
                break
    if not type_label:
        # Fallback vers le badge ou le code
        type_label = m.movement_type or "Non spécifié"
    
    return templates.TemplateResponse(
        request,
        "mouvement_detail.html",
        {
            "mouvement": m,
            "type_badge": type_badge,
            "status_badge": status_badge,
            "type_label": type_label,
            "uf_responsable_label": uf_responsable_label,
            "uf_soins_label": uf_soins_label,
            "uf_hebergement_label": uf_hebergement_label,
            "chambre_info": chambre_info,
            "lit_info": lit_info,
            "movement_type_options": movement_type_options
        }
    )


@router.get("/{mouvement_id}/edit", response_class=HTMLResponse)
def edit_mouvement(mouvement_id: int, request: Request, session=Depends(get_session)):
    # Temporary: skip GHT context check for testing
    # if not getattr(request.state, "ght_context", None):
    #     raise HTTPException(status_code=307, detail="Active GHT context required")

    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)

    # Refresh venue and dossier for context
    session.refresh(m, ["venue"])
    if m.venue:
        session.refresh(m.venue, ["dossier"])
        if m.venue.dossier:
            session.refresh(m.venue.dossier, ["patient"])

    # --- Venue options (single, readonly) ---
    venue_options = []
    if m.venue:
        venue_options = [{"value": str(m.venue_id), "label": m.venue.label or f"Venue #{m.venue_id}"}]

    # --- Type options (same as create) ---
    type_options = [
        {"value": "ADT^A01", "label": "Admission"},
        {"value": "ADT^A02", "label": "Transfert"},
        {"value": "ADT^A03", "label": "Sortie"},
        {"value": "ADT^A04", "label": "Consultation"},
    ]
    type_value = m.type if getattr(m, 'type', None) else (f"ADT^{m.trigger_event}" if getattr(m, 'trigger_event', None) else None)

    # --- UF options (same as create) ---
    from app.models_structure import UniteFonctionnelle, UniteHebergement, Chambre, Lit
    uf_options = []
    selected_uf_identifier = None  # For form value (string identifier)
    selected_uf_db_id = None      # For database queries (int id)
    selected_uh_id = None
    selected_chambre_id = None
    selected_lit_id = None

    # First, try to get UF from stored values in the movement
    if getattr(m, 'uf_responsabilite', None):
        # Find UF by identifier from stored uf_responsabilite
        uf_resp = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == m.uf_responsabilite)).first()
        if uf_resp:
            selected_uf_db_id = uf_resp.id
            selected_uf_identifier = uf_resp.identifier

    # Always try to extract structure from existing location to complete missing info
    if m.location:
        # Parse location like "SERV-A^LIT-101" or "UH-001^CH-001" to extract components
        parts = m.location.split('^')
        if len(parts) >= 2:
            uh_part = parts[0]
            chambre_part = parts[1] if len(parts) > 1 else None
            
            # Try to find chambre by identifier
            if chambre_part:
                chambre = session.exec(select(Chambre).where(Chambre.identifier == chambre_part)).first()
                if chambre:
                    selected_chambre_id = chambre.id
                    selected_lit_id = chambre.id  # Assuming lit_id maps to chambre_id for now
                    selected_uh_id = chambre.unite_hebergement_id
                    # If we don't have UF from uf_responsabilite, get it from chambre
                    if not selected_uf_db_id and chambre.unite_hebergement and chambre.unite_hebergement.unite_fonctionnelle:
                        selected_uf_db_id = chambre.unite_hebergement.unite_fonctionnelle_id
                        selected_uf_identifier = chambre.unite_hebergement.unite_fonctionnelle.identifier
                else:
                    # If chambre not found, try to find UH by identifier
                    uh = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == uh_part)).first()
                    if uh:
                        selected_uh_id = uh.id
                        # If we don't have UF from uf_responsabilite, get it from UH
                        if not selected_uf_db_id and uh.unite_fonctionnelle:
                            selected_uf_db_id = uh.unite_fonctionnelle_id
                            selected_uf_identifier = uh.unite_fonctionnelle.identifier

    # Get UF options (same logic as create)
    ej_context = getattr(request.state, "ej_context", None)
    ej_id = getattr(ej_context, "id", None) if ej_context else None

    uf_ids = set()
    if ej_id:
        # Récupérer toutes les UF de l'EJ via la hiérarchie EG -> Pole -> Service -> UF
        from app.models_structure_fhir import EntiteGeographique
        from app.models_structure import Pole, Service

        # EJ -> Entites Geographiques
        entites_geo = session.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej_id)).all()

        for eg in entites_geo:
            # EG -> Poles
            poles = session.exec(select(Pole).where(Pole.entite_geo_id == eg.id)).all()

            for pole in poles:
                # Pole -> Services
                services = session.exec(select(Service).where(Service.pole_id == pole.id)).all()

                for service in services:
                    # Service -> UF
                    service_ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id)).all()
                    uf_ids.update(uf.id for uf in service_ufs)

    # Fallback: utiliser toutes les UF
    if not uf_ids:
        all_ufs = session.exec(select(UniteFonctionnelle).order_by(UniteFonctionnelle.name)).all()
        uf_ids.update(uf.id for uf in all_ufs)

    # Récupérer les objets UF et créer les options
    ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.id.in_(uf_ids))).all()
    for uf in ufs:
        label = uf.short_name if getattr(uf, 'short_name', None) and uf.short_name and uf.short_name.strip() else uf.name
        uf_options.append({"value": uf.identifier, "label": label})

    # --- UH options (for selected UF) ---
    uh_options = []
    if selected_uf_db_id:
        uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == selected_uf_db_id)).all()
        for uh in uhs:
            label = f"{uh.identifier} — {uh.name}"
            uh_options.append({"value": str(uh.id), "label": label})

    # --- Chambre options (for selected UH) ---
    chambre_options = []
    if selected_uh_id:
        chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == selected_uh_id)).all()
        for chambre in chambres:
            label = f"{chambre.identifier} — {chambre.name}" if chambre.name else chambre.identifier
            chambre_options.append({"value": str(chambre.id), "label": label})

    # --- Lit options (for selected chambre) ---
    lit_options = []
    if selected_chambre_id:
        # For now, assume lit_id maps to chambre_id
        # In a real implementation, you might have a separate Lit model
        chambre = session.get(Chambre, selected_chambre_id)
        if chambre:
            lit_options.append({"value": str(chambre.id), "label": chambre.identifier})

    # --- Build fields (same order and structure as create) ---
    fields = [
        {
            "label": "Venue (Séjour) *",
            "name": "venue_id",
            "type": "select",
            "options": venue_options,
            "value": str(m.venue_id),
            "required": True,
            "readonly": True,
            "help": "Sélectionnez la venue concernée par ce mouvement"
        },
        {
            "label": "Type de mouvement *",
            "name": "type",
            "type": "select",
            "options": type_options,
            "value": type_value,
            "required": True,
            "help": "Options filtrées selon l'état actuel de la venue et le type de séjour"
        },
        {
            "label": "Date et heure *",
            "name": "when",
            "type": "datetime-local",
            "value": m.when.strftime('%Y-%m-%dT%H:%M') if m.when else '',
            "required": True,
            "help": "Date et heure du mouvement"
        },
        {
            "label": "Unité médicale (UF)",
            "name": "uf_id",
            "type": "select",
            "options": uf_options,
            "value": selected_uf_identifier,
            "help": "Sélectionnez l'UF médicale concernée"
        },
        {
            "label": "Unité de Soins (UF Soins)",
            "name": "uf_soins_id",
            "type": "select",
            "options": uf_options,  # Même options que l'UF principale
            "value": getattr(m, 'uf_soins_code', None),
            "help": "Sélectionnez l'unité de soins (optionnel)"
        },
        {
            "label": "Unité d'Hébergement (UH)",
            "name": "uh_id",
            "type": "select",
            "options": uh_options,
            "value": str(selected_uh_id) if selected_uh_id else None,
            "help": "Sélectionnez l'unité d'hébergement liée à l'UF"
        },
        {
            "label": "Chambre",
            "name": "chambre_id",
            "type": "select",
            "options": chambre_options,
            "value": str(selected_chambre_id) if selected_chambre_id else None,
            "help": "Sélectionnez d'abord une UH",
            "depends_on": "uh_id"
        },
        {
            "label": "Lit",
            "name": "lit_id",
            "type": "select",
            "options": lit_options,
            "value": str(selected_lit_id) if selected_lit_id else None,
            "help": "Sélectionnez d'abord une chambre",
            "depends_on": "chambre_id"
        },
        {
            "label": "Depuis (départ)",
            "name": "from_location",
            "type": "text",
            "value": getattr(m, 'from_location', None),
            "help": "Pour les transferts : lieu de départ"
        },
        {
            "label": "Vers (arrivée)",
            "name": "to_location",
            "type": "text",
            "value": getattr(m, 'to_location', None),
            "help": "Pour les transferts : lieu d'arrivée"
        },
        {
            "label": "Raison / Motif",
            "name": "reason",
            "type": "text",
            "value": getattr(m, 'reason', None),
            "help": "Motif du mouvement (issu du vocabulaire)"
        },
        {
            "label": "Numéro de séquence",
            "name": "mouvement_seq",
            "type": "number",
            "value": m.mouvement_seq,
            "readonly": True,
            "help": "Généré automatiquement - ne modifier que si nécessaire"
        },
        {
            "label": "Raison du mouvement",
            "name": "movement_reason",
            "type": "text",
            "value": getattr(m, 'movement_reason', None),
            "help": "Raison détaillée du mouvement"
        },
        {
            "label": "Statut du mouvement",
            "name": "status",
            "type": "select",
            "options": [
                {"value": "active", "label": "Actif"},
                {"value": "completed", "label": "Terminé"},
                {"value": "cancelled", "label": "Annulé"},
                {"value": "pending", "label": "En attente"},
            ],
            "value": getattr(m, 'status', None),
            "readonly": True,
            "hidden": True,
            "help": "Indicateur interne, non modifiable."
        },
    ]

    return templates.TemplateResponse(
        request,
        "form.html",
        {
            "title": "Modifier mouvement",
            "fields": fields,
            "action_url": f"/mouvements/{mouvement_id}/edit",
            "back_url": f"/mouvements?venue_id={m.venue_id}",
        }
    )


@router.post("/{mouvement_id}/edit")
def update_mouvement(
    mouvement_id: int,
    venue_id: int = Form(...),
    type: str = Form(...),
    when: str = Form(...),
    uf_id: str = Form(None),
    uf_soins_id: str = Form(None),
    uh_id: int = Form(None),
    chambre_id: int = Form(None),
    lit_id: int = Form(None),
    from_location: str = Form(None),
    to_location: str = Form(None),
    reason: str = Form(None),
    mouvement_seq: int = Form(...),
    movement_reason: str = Form(None),
    session=Depends(get_session),
    request: Request = None,
):
    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)
    
    # Import required models
    from app.models_structure import Chambre, UniteHebergement, UniteFonctionnelle
    
    # Build location from structure if provided
    final_location = None
    uf_responsabilite = None
    uf_soins_code = None
    uf_soins_label = None
    
    if chambre_id:
        # Build location from chambre
        chambre = session.get(Chambre, chambre_id)
        if chambre:
            final_location = f"{chambre.unite_hebergement.identifier if chambre.unite_hebergement else 'UH'}^{chambre.identifier}"
            
            # Update UF responsabilite from chambre's UH's UF
            if chambre.unite_hebergement and chambre.unite_hebergement.unite_fonctionnelle:
                uf_responsabilite = chambre.unite_hebergement.unite_fonctionnelle.identifier
    elif uh_id:
        # Build location from UH only
        uh = session.get(UniteHebergement, uh_id)
        if uh:
            final_location = f"{uh.identifier}^"
            
            # Update UF responsabilite from UH's UF
            if uh.unite_fonctionnelle:
                uf_responsabilite = uh.unite_fonctionnelle.identifier
    
    # Handle UF soins if provided
    if uf_soins_id:
        uf_soins_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == uf_soins_id)).first()
        if uf_soins_obj:
            uf_soins_code = uf_soins_obj.identifier
            uf_soins_label = uf_soins_obj.short_name if getattr(uf_soins_obj, 'short_name', None) and uf_soins_obj.short_name and uf_soins_obj.short_name.strip() else uf_soins_obj.name
    
    # Handle UF responsabilite if provided directly
    if uf_id:
        uf_resp_obj = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == uf_id)).first()
        if uf_resp_obj:
            uf_responsabilite = uf_resp_obj.identifier
    
    try:
        m.venue_id = venue_id
        m.type = type
        # Keep trigger_event in sync with the selected type
        if type:
            parts = type.split('^', 1)
            m.trigger_event = parts[1] if len(parts) == 2 else None
        else:
            m.trigger_event = None
        
        # Parse datetime, handle empty string
        if when:
            m.when = datetime.fromisoformat(when)
        else:
            m.when = None
            
        m.location = final_location
        m.from_location = from_location
        m.to_location = to_location
        m.reason = reason
        m.mouvement_seq = mouvement_seq
        m.movement_reason = movement_reason
        
        # Update UF fields
        m.uf_responsabilite = uf_responsabilite
        m.uf_soins_code = uf_soins_code
        m.uf_soins_label = uf_soins_label
        
        session.add(m)
        session.commit()
        
        # Refresh with relationships for emit_to_senders
        session.refresh(m)
        if m.venue:
            session.refresh(m.venue, ["dossier"])
            if m.venue.dossier:
                session.refresh(m.venue.dossier, ["patient"])
        
        emit_to_senders(m, "mouvement", session, operation="update")
        return RedirectResponse(url="/mouvements", status_code=303)
    except Exception as e:
        session.rollback()
        # Return error to user with proper template
        from app.middleware.flash import flash
        flash(request, f"Erreur lors de la modification: {str(e)}", "error")
        return RedirectResponse(url=f"/mouvements/{mouvement_id}/edit", status_code=303)


@router.post("/{mouvement_id}/delete")
def delete_mouvement(mouvement_id: int, request: Request, session=Depends(get_session)):
    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)
    session.delete(m); session.commit()
    emit_to_senders(m, "mouvement", session)
    return RedirectResponse(url="/mouvements", status_code=303)


# ============================================================================
# AJAX API Endpoints for Dynamic Form Updates (NO AUTH REQUIRED)
# ============================================================================
# These endpoints are accessible without GHT context since they're called by JavaScript

ajax_router = APIRouter(prefix="/mouvements/api", tags=["mouvements-ajax"])

@ajax_router.get("/chambres/{uh_id}")
def get_chambres_for_uh(uh_id: int, session=Depends(get_session)):
    """Return list of Chambres for a given UniteHebergement."""
    from app.models_structure import Chambre
    
    try:
        chambres = session.exec(
            select(Chambre).where(Chambre.unite_hebergement_id == uh_id)
        ).all()
        
        options = [
            {"value": str(c.id), "label": c.name} 
            for c in chambres
        ]
        return JSONResponse({"success": True, "options": options})
    except Exception as e:
        # Log the error for debugging
        import logging
        logging.error(f"Error getting chambres for UH {uh_id}: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@ajax_router.get("/unites_hebergement/{uf_id}")
def get_unites_hebergement_for_uf(uf_id: str, session=Depends(get_session)):
    """Return list of UniteHebergement for a given UniteFonctionnelle identifier."""
    from app.models_structure import UniteHebergement, UniteFonctionnelle
    
    try:
        # First get the UF object by identifier
        uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == uf_id)).first()
        if not uf:
            return JSONResponse({"success": False, "error": f"UF with identifier {uf_id} not found"}, status_code=404)
        
        # Get UH for this UF
        uhs = session.exec(
            select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf.id)
        ).all()
        
        options = [
            {"value": str(uh.id), "label": uh.name}
            for uh in uhs
        ]
        return JSONResponse({"success": True, "options": options})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@ajax_router.get("/lits/{chambre_id}")
def get_lits_for_chambre(chambre_id: int, session=Depends(get_session)):
    """Return list of Lits for a given Chambre."""
    from app.models_structure import Lit
    
    try:
        lits = session.exec(
            select(Lit).where(Lit.chambre_id == chambre_id)
        ).all()
        
        options = [
            {"value": str(l.id), "label": l.name} 
            for l in lits
        ]
        return JSONResponse({"success": True, "options": options})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@ajax_router.get("/reasons/{movement_type}")
def get_reasons_for_movement_type(movement_type: str, session=Depends(get_session)):
    """Return list of possible reasons/motifs for a given movement type."""
    try:
        # Get all movement reasons from vocabulary
        all_reason_options = get_vocabulary_options("movement-reason") or []
        
        # Filter based on movement_type according to IHE PAM specifications
        # Extract event code (e.g., "A01^Admission" -> "A01")
        event_code = movement_type.split('^')[0] if '^' in movement_type else movement_type
        
        # Mapping of IHE PAM event codes to appropriate reasons
        reason_mapping = {
            'A01': ['urgence', 'programmee', 'transfert_entrant', 'naissance'],  # Admission
            'A02': ['transfert_interne', 'mutation_service', 'changement_lit'],  # Transfer
            'A03': ['guerison', 'transfert_sortant', 'deces', 'contre_avis', 'domicile'],  # Discharge
            'A04': ['consultation', 'visite'],  # Registration
            'A05': ['preadmission', 'programmation'],  # Pre-admission
            'A06': ['mutation', 'reclassement'],  # Class change
            'A07': ['retour_consultation'],  # From consultation
            'A08': ['erreur'],  # Error
            'A11': ['annulation_admission'],  # Cancel admission
            'A12': ['annulation_transfert'],  # Cancel transfer
            'A13': ['annulation_sortie'],  # Cancel discharge
            'A21': ['permission_sortie'],  # Leave of absence
            'A22': ['retour_permission'],  # Return from leave
            'A38': ['annulation_preadmission']  # Cancel pre-admission
        }
        
        # Get appropriate reasons for this event, or return all if unknown event
        appropriate_codes = reason_mapping.get(event_code, [])
        
        if appropriate_codes:
            # Filter options to only include appropriate reasons
            filtered_options = [opt for opt in all_reason_options if opt.get('value') in appropriate_codes]
        else:
            # Unknown event type, return all options
            filtered_options = all_reason_options
        
        return JSONResponse({"success": True, "options": filtered_options})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)

# Edition UF
from app.models_structure import UniteFonctionnelle

@router.get("/uf/{uf_id}/edit", response_class=HTMLResponse)
def edit_uf_form(uf_id: int, request: Request, session=Depends(get_session)):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    fields = [
        {"label": "Identifiant UF", "name": "identifier", "type": "text", "value": uf.identifier, "required": True},
        {"label": "Nom", "name": "name", "type": "text", "value": uf.name, "required": True},
        {"label": "Nom court", "name": "short_name", "type": "text", "value": uf.short_name},
    ]
    return templates.TemplateResponse(request, "form.html", {
        "title": f"Éditer UF {uf.identifier}",
        "fields": fields,
        "action_url": f"/mouvements/uf/{uf_id}/edit",
        "back_url": "/mouvements/new"
    })

@router.post("/uf/{uf_id}/edit")
def update_uf(uf_id: int, identifier: str = Form(...), name: str = Form(...), short_name: str = Form(None), session=Depends(get_session), request: Request = None):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    uf.identifier = identifier
    uf.name = name
    uf.short_name = short_name
    session.add(uf)
    session.commit()
    return RedirectResponse(url="/mouvements/new", status_code=303)

# Suppression UF
@router.get("/uf/{uf_id}/delete", response_class=HTMLResponse)
def confirm_delete_uf(uf_id: int, request: Request, session=Depends(get_session)):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    return templates.TemplateResponse(request, "confirm_delete.html", {
        "title": f"Supprimer UF {uf.identifier}",
        "object_label": uf.name,
        "action_url": f"/mouvements/uf/{uf_id}/delete",
        "back_url": "/mouvements/new"
    })

@router.post("/uf/{uf_id}/delete")
def delete_uf(uf_id: int, session=Depends(get_session), request: Request = None):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    session.delete(uf)
    session.commit()
    return RedirectResponse(url="/mouvements/new", status_code=303)






