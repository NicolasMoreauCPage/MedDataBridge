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
            dossier_ids = [d.id for d in session.exec(select(Dossier).where(Dossier.entite_juridique_id == ej_context.id)).all()]
            if dossier_ids:
                venue_ids = [v.id for v in session.exec(select(Venue).where(Venue.dossier_id.in_(dossier_ids)).all())]
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
    from app.models_structure import UniteHebergement, Chambre, Lit, UniteFonctionnelle
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
    # Pré-remplir UF depuis la venue ou le dossier
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
            "label": "Unité Fonctionnelle (UF)",
            "name": "uf_id",
            "type": "select",
            "options": uf_options,
            "value": selected_venue.uf_responsabilite if (selected_venue and selected_venue.uf_responsabilite) else None,
            "help": "Sélectionnez l'UF concernée (pré-remplie si venue/dossier)"
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
            "options": [],
            "help": "Sélectionnez d'abord une UH",
            "depends_on": "uh_id"
        },
        {
            "label": "Lit",
            "name": "lit_id",
            "type": "select",
            "options": [],
            "help": "Sélectionnez d'abord une chambre",
            "depends_on": "chambre_id"
        },
        {
            "label": "Depuis (départ)",
            "name": "from_location",
            "type": "text",
            "help": "Pour les transferts : lieu de départ"
        },
        {
            "label": "Vers (arrivée)",
            "name": "to_location",
            "type": "text",
            "help": "Pour les transferts : lieu d'arrivée"
        },
        {
            "label": "Raison / Motif",
            "name": "reason",
            "type": "select" if reason_options else "text",
            "options": reason_options,
            "help": "Motif du mouvement (issu du vocabulaire)"
        },
        {
            "label": "Intervenant",
            "name": "performer",
            "type": "text",
            "help": "Nom de la personne ayant effectué le mouvement"
        },
        {
            "label": "Rôle de l'intervenant",
            "name": "performer_role",
            "type": "text",
            "help": "Fonction de l'intervenant (ex: IDE, Médecin)"
        },
        {
            "label": "Note / Commentaire",
            "name": "note",
            "type": "textarea",
            "help": "Remarque libre"
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
    uh_id: int = Form(None),
    chambre_id: int = Form(None),
    lit_id: int = Form(None),
    location: str = Form(None),
    from_location: str = Form(None),
    to_location: str = Form(None),
    reason: str = Form(None),
    performer: str = Form(None),
    status: str = Form(None),
    note: str = Form(None),
    mouvement_seq: int | None = Form(None),
    movement_type: str = Form(None),
    movement_reason: str = Form(None),
    performer_role: str = Form(None),
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
    if requires_location and not location:
        raise HTTPException(status_code=400, detail="La localisation est obligatoire pour ce type de mouvement")

    # Sequence generation (always generate new, ignore form value)
    seq = get_next_sequence(session, "mouvement")
    mapped_movement_type = movement_type
    if trigger_event in event_mapping:
        mapped_movement_type = event_mapping[trigger_event][0]
    m = Mouvement(
        venue_id=venue_id,
        type=type,
        when=when_dt,
        location=location,
        from_location=from_location,
        to_location=to_location,
        reason=reason,
        performer=performer,
        status=status,
        note=note,
        mouvement_seq=seq,
        movement_type=mapped_movement_type,
        movement_reason=movement_reason,
        performer_role=performer_role,
        trigger_event=trigger_event,
    )
    session.add(m)
    session.commit()
    emit_to_senders(m, "mouvement", session)
    return RedirectResponse(url=f"/mouvements?venue_id={venue_id}", status_code=303)

@router.get("/{mouvement_id}", response_class=HTMLResponse)
def mouvement_detail(mouvement_id: int, request: Request, session=Depends(get_session)):
    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)
    # Affichage uniquement du badge métier (movement_type)
    type_badge = get_type_badge(getattr(m, 'movement_type', None))
    status_badge = get_status_badge(getattr(m, 'status', 'pending'))
    from app.services.vocabulary_lookup import get_vocabulary_options
    movement_type_options = get_vocabulary_options("movement-nature") or []
    return templates.TemplateResponse(
        request,
        "mouvement_detail.html",
        {
            "mouvement": m,
            "type_badge": type_badge,
            "status_badge": status_badge,
                "movement_type_options": movement_type_options
        }
    )


@router.get("/{mouvement_id}/edit", response_class=HTMLResponse)
def edit_mouvement(mouvement_id: int, request: Request, session=Depends(get_session)):
    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)

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

    # --- Reason options (dropdown if available) ---
    reason_options = get_vocabulary_options("movement-reason")
    reason_field_type = "select" if reason_options else "text"

    # --- Movement nature options ---
    movement_nature_options = get_vocabulary_options("movement-nature") or [
        {"value": c, "label": l} for c, l in [
            ("S", "Séjour"), ("H", "Hospitalisation"), ("M", "Mouvement"), ("L", "Localisation"), ("D", "Diagnostic"), ("SM", "Sous-mouvement")
        ]
    ]

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
            "label": "Localisation complète",
            "name": "location",
            "type": "text",
            "value": m.location,
            "help": "Code de localisation (ex: SERV-A^LIT-101) - généré automatiquement si structure sélectionnée"
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
            "type": reason_field_type,
            "options": reason_options,
            "value": getattr(m, 'reason', None),
            "help": "Motif du mouvement (issu du vocabulaire)"
        },
        {
            "label": "Intervenant",
            "name": "performer",
            "type": "text",
            "value": getattr(m, 'performer', None),
            "help": "Nom de la personne ayant effectué le mouvement"
        },
        {
            "label": "Rôle de l'intervenant",
            "name": "performer_role",
            "type": "text",
            "value": getattr(m, 'performer_role', None),
            "help": "Fonction de l'intervenant (ex: IDE, Médecin)"
        },
        {
            "label": "Note / Commentaire",
            "name": "note",
            "type": "textarea",
            "value": getattr(m, 'note', None),
            "help": "Remarque libre"
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
            "label": "Type de mouvement (nature)",
            "name": "movement_type",
            "type": "select",
            "options": movement_nature_options,
            "value": getattr(m, 'movement_type', None),
            "help": "Nature du mouvement (vocabulaire)"
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

    session.refresh(m, ["venue"])
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
    location: str = Form(None),
    from_location: str = Form(None),
    to_location: str = Form(None),
    reason: str = Form(None),
    performer: str = Form(None),
    status: str = Form(None),
    note: str = Form(None),
    mouvement_seq: int = Form(...),
    movement_type: str = Form(None),
    movement_reason: str = Form(None),
    performer_role: str = Form(None),
    session=Depends(get_session),
    request: Request = None,
):
    m = session.get(Mouvement, mouvement_id)
    if not m:
        return templates.TemplateResponse(request, "not_found.html", {"request": request, "title": "Mouvement introuvable"}, status_code=404)
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
            
        m.location = location
        m.from_location = from_location
        m.to_location = to_location
        m.reason = reason
        m.performer = performer
        m.status = status
        m.note = note
        m.mouvement_seq = mouvement_seq
        m.movement_type = movement_type
        m.movement_reason = movement_reason
        m.performer_role = performer_role
        
        session.add(m)
        session.commit()
        
        # Refresh with relationships for emit_to_senders
        session.refresh(m)
        if m.venue:
            session.refresh(m.venue, ["dossier"])
            if m.venue.dossier:
                session.refresh(m.venue.dossier, ["patient"])
        
        emit_to_senders(m, "mouvement", session)
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
        reason_options = get_vocabulary_options("movement-reason") or []
        
        # Filter based on movement_type if needed
        # For now, return all available reasons
        # Future: implement type-specific reason filtering based on IHE PAM spec
        
        return JSONResponse({"success": True, "options": reason_options})
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






