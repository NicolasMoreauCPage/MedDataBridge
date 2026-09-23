from fastapi import APIRouter, Depends, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import Request as FastAPIRequest
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus
from app.db import get_session
from app.models_structure import UniteFonctionnelle
from app.services.emit_on_create import emit_to_senders
from app.services.bed_assignment import (
    BedAssignmentError,
    assign_patient_to_bed as assign_patient_to_bed_use_case,
)
from app.services.bed_plan import build_bed_plan, search_bed_plan_patients
from app.services.movement_listing import (
    MovementListContextError,
    build_movement_list_view,
    load_movement_list,
    movement_status_badge,
    movement_type_badge,
)
from app.services.movement_form_context import (
    MovementFormContextError,
    build_edit_movement_form,
    build_new_movement_form,
)
from app.services.movement_creation import (
    MovementCreationError,
    create_patient_movement,
)
from app.services.movement_details import MovementDetailsError, load_movement_details
from app.services.movement_update import update_patient_movement
from app.services.movement_options import (
    MovementOptionParentNotFound,
    accommodation_options,
    bed_options,
    movement_reason_options,
    room_options,
)
from app.services.movement_deletion import (
    MovementDeletionError,
    delete_patient_movement,
)
from app.dependencies.ght import require_ght_context


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(
    prefix="/mouvements",
    tags=["mouvements"],
    dependencies=[Depends(require_ght_context)]
)


@router.get("/plan-lits", response_class=HTMLResponse)
def plan_lits(
    request: Request,
    session = Depends(get_session),
    uf_filter: Optional[str] = Query(None, description="Filtrer par UF"),
    service_filter: Optional[str] = Query(None, description="Filtrer par Service"),
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: free, occupied, closed"),
    entity_type: Optional[str] = Query(None, description="Restreindre à une entité de structure: eg, pole, service, uf, uh, chambre, lit"),
    entity_id: Optional[int] = Query(None, description="ID de l'entité désignée par entity_type"),
):
    """
    Vue plan de lits : affiche tous les lits organisés par service/UF/UH/chambre
    avec statut en temps réel et actions rapides pour affecter des patients.

    `entity_type`/`entity_id` permettent de restreindre l'affichage à une entité précise de la
    hiérarchie de structure (utilisé par les pages de détail eg/pole/service/uf/uh pour afficher
    leur propre plan de lits plutôt qu'une page "bientôt disponible").
    """
    eg_context = getattr(request.state, "eg_context", None)
    ej_context = getattr(request.state, "ej_context", None)
    eg_id = getattr(eg_context, "id", None) if eg_context else None
    ej_id = getattr(ej_context, "id", None) if ej_context and not eg_id else None
    plan = build_bed_plan(
        session,
        eg_id=eg_id,
        ej_id=ej_id,
        ej_from_eg_id=(
            getattr(eg_context, "entite_juridique_id", None) if eg_context else None
        ),
        uf_filter=uf_filter,
        service_filter=service_filter,
        status_filter=status_filter,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    context = {
        "request": request,
        **plan,
        "breadcrumbs": [
            {"label": "Accueil", "url": "/"},
            {"label": "Mouvements", "url": "/mouvements"},
            {"label": "Plan de lits", "url": "/mouvements/plan-lits"},
        ],
    }
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "plan_lits.html",
        context,
    )


@router.post("/plan-lits/assign")
def assign_patient_to_bed(
    lit_id: int = Form(...),
    selected_patient_id: int = Form(...),
    session=Depends(get_session),
):
    """Affecte une venue active au lit et émet le transfert créé."""
    try:
        result = assign_patient_to_bed_use_case(
            session,
            bed_id=lit_id,
            patient_id=selected_patient_id,
        )
    except BedAssignmentError as exc:
        return RedirectResponse(
            url="/mouvements/plan-lits?error=" + quote_plus(str(exc)),
            status_code=303,
        )

    if result.movement is not None:
        emit_to_senders(result.movement, "mouvement", session)
    return RedirectResponse(
        url="/mouvements/plan-lits?message=" + quote_plus(result.message),
        status_code=303,
    )

@router.get("", response_class=HTMLResponse)
def list_mouvements(
    request: Request,
    venue_id: Optional[int] = Query(None, description="ID de la venue dont on veut voir les mouvements"),
    dossier_id: Optional[int] = Query(None, description="ID du dossier dont on veut voir les mouvements"),
    include_cancelled: bool = Query(False, description="Inclure les mouvements annulés dans la liste"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="Ordre de tri par date"),
    movement_type: Optional[str] = Query(None, alias="type", description="Filtrer par type HL7 (ADT^A01, A02, ... )"),
    status: Optional[str] = Query(None, alias="status", description="Filtrer par statut du mouvement"),
    location_filter: Optional[str] = Query(None, alias="location", description="Filtrer par localisation (contient)"),
    session=Depends(get_session)
):
    ej_context = getattr(request.state, "ej_context", None)
    try:
        result = load_movement_list(
            session,
            venue_id=venue_id,
            dossier_id=dossier_id,
            ej_id=getattr(ej_context, "id", None) if ej_context else None,
            include_cancelled=include_cancelled,
            order=order,
            movement_type=movement_type,
            status=status,
            location_filter=location_filter,
        )
    except MovementListContextError as exc:
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "error.html",
            {
                "title": exc.title,
                "message": exc.message,
                "back_url": exc.back_url,
            },
            status_code=exc.status_code,
        )
    view = build_movement_list_view(
        result,
        venue_id=venue_id,
        dossier_id=dossier_id,
        include_cancelled=include_cancelled,
        order=order,
        movement_type=movement_type,
        status=status,
        location_filter=location_filter,
    )
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "list.html",
        view,
    )



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
    venue_context = getattr(request.state, "venue_context", None)
    dossier_context = getattr(request.state, "dossier_context", None)
    try:
        form = build_new_movement_form(
            session,
            venue_id=venue_id,
            dossier_id=dossier_id,
            venue_context_id=getattr(venue_context, "id", None),
            dossier_context_id=getattr(dossier_context, "id", None),
        )
    except MovementFormContextError as exc:
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "error.html",
            {
                "title": exc.title,
                "message": exc.message,
                "back_url": exc.back_url,
            },
            status_code=exc.status_code,
        )
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "form.html",
        {"title": form.title, "fields": form.fields, "back_url": form.back_url},
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
    try:
        movement = create_patient_movement(
            session,
            venue_id=venue_id,
            type_code=type,
            when=datetime.fromisoformat(when),
            uf_id=uf_id,
            uf_soins_identifier=uf_soins_id,
            uh_id=uh_id,
            chambre_id=chambre_id,
            lit_id=lit_id,
            from_location=from_location,
            to_location=to_location,
            reason=reason,
            movement_reason=movement_reason,
        )
    except (MovementCreationError, ValueError) as exc:
        status_code = getattr(exc, "status_code", 400)
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    emit_to_senders(movement, "mouvement", session)
    return RedirectResponse(
        url=f"/mouvements?venue_id={venue_id}",
        status_code=303,
    )


@router.get("/{mouvement_id}", response_class=HTMLResponse)
def mouvement_detail(mouvement_id: int, request: Request, session=Depends(get_session)):
    require_ght_context(request)
    try:
        details = load_movement_details(session, mouvement_id)
    except MovementDetailsError:
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "not_found.html",
            {"title": "Mouvement introuvable"},
            status_code=404,
        )

    movement = details.movement
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "mouvement_detail.html",
        {
            "mouvement": movement,
            "type_badge": movement_type_badge(movement.movement_type),
            "status_badge": movement_status_badge(movement.status or "pending"),
            "type_label": details.type_label,
            "uf_responsable_label": details.uf_responsable_label,
            "uf_soins_label": details.uf_soins_label,
            "uf_hebergement_label": details.uf_hebergement_label,
            "chambre_info": details.chambre_info,
            "lit_info": details.lit_info,
            "movement_type_options": details.movement_type_options,
        },
    )



@router.get("/{mouvement_id}/edit", response_class=HTMLResponse)
def edit_mouvement(mouvement_id: int, request: Request, session=Depends(get_session)):
    ej_context = getattr(request.state, "ej_context", None)
    try:
        form = build_edit_movement_form(
            session,
            movement_id=mouvement_id,
            ej_context_id=getattr(ej_context, "id", None),
        )
    except MovementFormContextError:
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "not_found.html",
            {"title": "Mouvement introuvable"},
            status_code=404,
        )

    return get_templates_with_filters(request).TemplateResponse(
        request,
        "form.html",
        {
            "title": form.title,
            "fields": form.fields,
            "action_url": f"/mouvements/{mouvement_id}/edit",
            "back_url": form.back_url,
        },
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
    try:
        movement = update_patient_movement(
            session,
            movement_id=mouvement_id,
            venue_id=venue_id,
            type_code=type,
            when=datetime.fromisoformat(when),
            uf_identifier=uf_id,
            uf_soins_identifier=uf_soins_id,
            uh_id=uh_id,
            chambre_id=chambre_id,
            lit_id=lit_id,
            from_location=from_location,
            to_location=to_location,
            reason=reason,
            movement_reason=movement_reason,
        )
    except (MovementCreationError, ValueError) as exc:
        status_code = getattr(exc, "status_code", 400)
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    emit_to_senders(movement, "mouvement", session, operation="update")
    return RedirectResponse(
        url=f"/mouvements?venue_id={movement.venue_id}",
        status_code=303,
    )



@router.post("/{mouvement_id}/delete")
def delete_mouvement(mouvement_id: int, request: Request, session=Depends(get_session)):
    try:
        venue_id = delete_patient_movement(
            session,
            movement_id=mouvement_id,
            before_delete=lambda movement: emit_to_senders(
                movement,
                "mouvement",
                session,
                operation="delete",
            ),
        )
    except MovementDeletionError:
        return get_templates_with_filters(request).TemplateResponse(
            request,
            "not_found.html",
            {"title": "Mouvement introuvable"},
            status_code=404,
        )
    return RedirectResponse(
        url=f"/mouvements?venue_id={venue_id}",
        status_code=303,
    )


# ============================================================================
# AJAX API Endpoints for Dynamic Form Updates (NO AUTH REQUIRED)
# ============================================================================
# These endpoints are accessible without GHT context since they're called by JavaScript

ajax_router = APIRouter(prefix="/mouvements/api", tags=["mouvements-ajax"])

@ajax_router.get("/chambres/{uh_id}")
def get_chambres_for_uh(uh_id: int, session=Depends(get_session)):
    """Return list of Chambres for a given UniteHebergement."""
    return JSONResponse({"success": True, "options": room_options(session, uh_id)})


@ajax_router.get("/unites_hebergement/{uf_id}")
def get_unites_hebergement_for_uf(uf_id: str, session=Depends(get_session)):
    """Return list of UniteHebergement for a given UniteFonctionnelle identifier."""
    try:
        options = accommodation_options(session, uf_id)
    except MovementOptionParentNotFound as exc:
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=404,
        )
    return JSONResponse({"success": True, "options": options})


@ajax_router.get("/lits/{chambre_id}")
def get_lits_for_chambre(chambre_id: int, session=Depends(get_session)):
    """Return list of Lits for a given Chambre."""
    return JSONResponse(
        {"success": True, "options": bed_options(session, chambre_id)}
    )


@ajax_router.get("/reasons/{movement_type}")
def get_reasons_for_movement_type(movement_type: str, session=Depends(get_session)):
    """Return list of possible reasons/motifs for a given movement type."""
    return JSONResponse(
        {"success": True, "options": movement_reason_options(movement_type)}
    )

# Edition UF
@router.get("/uf/{uf_id}/edit", response_class=HTMLResponse)
def edit_uf_form(uf_id: int, request: Request, session=Depends(get_session)):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    fields = [
        {"label": "Identifiant UF", "name": "identifier", "type": "text", "value": uf.identifier or '', "required": True},
        {"label": "Nom", "name": "name", "type": "text", "value": uf.name or '', "required": True},
        {"label": "Nom court", "name": "short_name", "type": "text", "value": uf.short_name or ''},
    ]
    return get_templates_with_filters(request).TemplateResponse(request, "form.html", {
        "title": f"Éditer UF {uf.identifier}",
        "fields": fields,
        "action_url": f"/mouvements/uf/{uf_id}/edit",
        "back_url": "/mouvements/new"
    })

@router.post("/uf/{uf_id}/edit")
def update_uf(uf_id: int, identifier: str = Form(...), name: str = Form(...), short_name: str = Form(None), session=Depends(get_session), request: Request = None):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
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
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    return get_templates_with_filters(request).TemplateResponse(request, "confirm_delete.html", {
        "title": f"Supprimer UF {uf.identifier}",
        "object_label": uf.name,
        "action_url": f"/mouvements/uf/{uf_id}/delete",
        "back_url": "/mouvements/new"
    })

@router.post("/uf/{uf_id}/delete")
def delete_uf(uf_id: int, session=Depends(get_session), request: Request = None):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        return get_templates_with_filters(request).TemplateResponse(request, "not_found.html", {"request": request, "title": "UF introuvable"}, status_code=404)
    session.delete(uf)
    session.commit()
    return RedirectResponse(url="/mouvements/new", status_code=303)

@ajax_router.get("/plan-lits/patient-search", response_class=JSONResponse)
def patient_search_api(
    q: str = Query(..., min_length=2, description="Nom, prénom, identifiant, etc."),
    limit: int = Query(10, ge=1, le=50),
    session=Depends(get_session),
):
    """API endpoint for patient autocomplete/search in plan-lits assignment popup."""
    return {
        "results": search_bed_plan_patients(session, query=q, limit=limit)
    }
