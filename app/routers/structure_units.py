"""Routes des unités d'hébergement."""
import logging
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.services.structure_schedule import apply_scheduled_status, form_datetime_to_hl7, hl7_to_form_datetime
from app.services.vocabulary_lookup import get_vocabulary_options
from app.schemas.structure import (
    UniteHebergementRead,
)
from app.models_structure import (
    UniteFonctionnelle,
    UniteHebergement, Chambre, Lit,
    LocationStatus, LocationMode, LocationPhysicalType,
)
from app.routers.structure_router_base import (
    DEFAULT_API_PAGE_SIZE,
    MAX_API_PAGE_SIZE,
    execute_paginated as _execute_paginated,
    get_templates_with_filters,
    router,
)

logger = logging.getLogger(__name__)

@router.get("/uh", response_class=HTMLResponse)
def list_unites_hebergement(
    request: Request,
    session: Session = Depends(get_session),
    uf_id: Optional[int] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None
):
    # Construction de la requête avec les filtres
    query = select(UniteHebergement)
    if uf_id:
        query = query.where(UniteHebergement.unite_fonctionnelle_id == uf_id)
    if mode:
        query = query.where(UniteHebergement.mode == mode)
    if status:
        query = query.where(UniteHebergement.status == status)
    
    uhs = session.exec(query).all()
    changed = apply_scheduled_status(uhs)

    # Récupération des UFs pour le filtre
    ufs = session.exec(select(UniteFonctionnelle)).all()
    if apply_scheduled_status(ufs):
        changed = True
    if changed:
        session.commit()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/uh.html",
        {
            "request": request,
            "unites_hebergement": uhs,
            "unites_fonctionnelles": ufs,
            "mode_options": get_vocabulary_options("location-mode"),
            "status_options": get_vocabulary_options("location-status"),
            "selected_uf_id": uf_id,
            "selected_mode": mode,
            "selected_status": status
        }
    )

@router.get("/api/uh", response_model=List[UniteHebergementRead])
def list_unites_hebergement_api(
    response: Response,
    session: Session = Depends(get_session),
    uf_id: Optional[int] = None,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    query = select(UniteHebergement)
    if uf_id:
        query = query.where(UniteHebergement.unite_fonctionnelle_id == uf_id)
    uhs = _execute_paginated(
        session,
        response,
        query,
        order_by=(UniteHebergement.name, UniteHebergement.id),
        skip=skip,
        limit=limit,
    )
    if apply_scheduled_status(uhs):
        session.commit()
    return uhs

@router.get("/uh/new", response_class=HTMLResponse)
def new_unite_hebergement_form(
    request: Request,
    session: Session = Depends(get_session)
):
    ufs = session.exec(select(UniteFonctionnelle)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/uh_form.html",
        {
            "request": request,
            "unites_fonctionnelles": ufs,
            "mode_options": get_vocabulary_options("location-mode"),
            "status_options": get_vocabulary_options("location-status"),
            "activation_date_value": None,
            "deactivation_date_value": None,
        }
    )

@router.get("/uh/{uh_id}", response_class=HTMLResponse)
def view_unite_hebergement(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    """Vue détaillée d'une UH avec ses chambres"""
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    changed = apply_scheduled_status([uh])

    # Charger les chambres liées à cette UH avec leurs lits
    chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh_id)).all()
    # Eager-load lits for each chambre so template can access them
    for chambre in chambres:
        lits = session.exec(select(Lit).where(Lit.chambre_id == chambre.id)).all()
        if apply_scheduled_status(lits):
            changed = True
        # attach lits to the chambre instance for template rendering
        setattr(chambre, "lits", lits)
    if apply_scheduled_status(chambres):
        changed = True
    if changed:
        session.commit()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/uh_detail.html",
        {
            "request": request,
            "uh": uh,
            "chambres": chambres
        }
    )

@router.get("/uh/{uh_id}/edit", response_class=HTMLResponse)
def edit_unite_hebergement_form(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    changed = apply_scheduled_status([uh])

    ufs = session.exec(select(UniteFonctionnelle)).all()
    if apply_scheduled_status(ufs):
        changed = True
    if changed:
        session.commit()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/uh_form.html",
        {
            "request": request,
            "uh": uh,
            "unites_fonctionnelles": ufs,
            "mode_options": get_vocabulary_options("location-mode"),
            "status_options": get_vocabulary_options("location-status"),
            "activation_date_value": hl7_to_form_datetime(getattr(uh, "activation_date", None)),
            "deactivation_date_value": hl7_to_form_datetime(getattr(uh, "deactivation_date", None)),
        }
    )

@router.post("/uh", response_model=UniteHebergementRead)
async def create_unite_hebergement(
    request: Request,
    session: Session = Depends(get_session)
):
    form = await request.form()
    mode_value = form.get("mode") or LocationMode.INSTANCE
    status_value = form.get("status") or LocationStatus.ACTIVE
    uh = UniteHebergement(
        name=form["name"],
        identifier=form["identifier"],
        unite_fonctionnelle_id=int(form["unite_fonctionnelle_id"]),
        mode=LocationMode(mode_value),
        status=LocationStatus(status_value),
        physical_type=LocationPhysicalType.WA,  # Une UH est toujours de type "wa" (ward)
    )
    uh.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    uh.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([uh])
    session.add(uh)
    session.commit()
    session.refresh(uh)
    return RedirectResponse(url="/structure/uh", status_code=303)

@router.post("/uh/{uh_id}", response_model=UniteHebergementRead)
async def update_unite_hebergement(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    
    form = await request.form()
    uh.name = form["name"]
    uh.identifier = form.get("identifier", uh.identifier)
    uh.unite_fonctionnelle_id = int(form["unite_fonctionnelle_id"])
    uh.mode = LocationMode(form.get("mode", uh.mode))
    uh.status = LocationStatus(form.get("status", uh.status))
    # Une UH est toujours de type "wa" (ward)
    uh.physical_type = LocationPhysicalType.WA
    uh.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    uh.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([uh])
    
    session.add(uh)
    session.commit()
    return RedirectResponse(url="/structure/uh", status_code=303)

# --- Suppression UH ---
@router.post("/uh/{uh_id}/delete")
def delete_unite_hebergement(
    uh_id: int,
    session: Session = Depends(get_session)
):
    """Supprime une unité d'hébergement et redirige vers la liste"""
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    
    # On vérifie d'abord qu'il n'y a plus de chambres actives
    chambres = session.exec(
        select(Chambre)
        .where(Chambre.unite_hebergement_id == uh_id)
        .where(Chambre.status == "active")
    ).all()
    
    if chambres:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer l'UH : des chambres actives y sont rattachées"
        )

    # Delete all inactive chambres and their lits first
    inactive_chambres = session.exec(
        select(Chambre)
        .where(Chambre.unite_hebergement_id == uh_id)
        .where(Chambre.status != "active")
    ).all()

    for chambre in inactive_chambres:
        # Delete all lits in the chambre
        lits = session.exec(
            select(Lit).where(Lit.chambre_id == chambre.id)
        ).all()
        for lit in lits:
            session.delete(lit)
        # Then delete the chambre
        session.delete(chambre)

    session.commit()
    session.delete(uh)
    session.commit()
    return RedirectResponse(url="/structure/uh", status_code=303)

# --- Chambres ---
