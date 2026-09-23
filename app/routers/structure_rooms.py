"""Routes des chambres et des lits."""
import logging
from typing import List, Optional

from fastapi import Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.services.structure_schedule import apply_scheduled_status, form_datetime_to_hl7, hl7_to_form_datetime
from app.services.vocabulary_lookup import get_vocabulary_options
from app.schemas.structure import (
    ChambreRead,
    LitRead,
)
from app.models_structure import (
    UniteHebergement, Chambre, Lit,
    LocationStatus, LocationMode, LocationPhysicalType,
)
from app.routers.structure_router_base import (
    DEFAULT_API_PAGE_SIZE,
    LIT_OPERATIONAL_STATUS_OPTIONS,
    MAX_API_PAGE_SIZE,
    api_router,
    execute_paginated as _execute_paginated,
    get_templates_with_filters,
    router,
)

logger = logging.getLogger(__name__)

@router.get("/chambres", response_class=HTMLResponse)
async def list_chambres(
    request: Request,
    session: Session = Depends(get_session),
    uh_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Chambre)
    if uh_id:
        query = query.where(Chambre.unite_hebergement_id == uh_id)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Chambre.name.ilike(like))
            | (Chambre.identifier.ilike(like))
        )
    
    chambres = session.exec(query.order_by(Chambre.name)).all()
    if apply_scheduled_status(chambres):
        session.commit()
    
    uhs = session.exec(select(UniteHebergement).order_by(UniteHebergement.name)).all()
    uh_map = {uh.id: uh.name for uh in uhs}
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/chambres_list.html",
        {
            "request": request,
            "chambres": chambres,
            "unites_hebergement": uhs,
            "uh_map": uh_map,
            "selected_uh_id": uh_id,
            "search_term": q,
        },
    )

@router.get("/chambres/new", response_class=HTMLResponse)
async def new_chambre_form(
    request: Request,
    uh_id: int,
    session: Session = Depends(get_session)
):
    """Formulaire de création d'une chambre"""
    uh = session.get(UniteHebergement, uh_id)
    if not uh:
        raise HTTPException(status_code=404, detail="Unité d'hébergement non trouvée")
    if apply_scheduled_status([uh]):
        session.commit()

    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/chambre_form.html",
        {
            "request": request,
            "unite_hebergement": uh,
            # Note: physical_type n'est pas fourni car une chambre est toujours de type "ro" (room)
            "status_options": get_vocabulary_options("location-status"),
            "activation_date_value": None,
            "deactivation_date_value": None,
        }
    )

@router.get("/chambres/{chambre_id}", response_class=HTMLResponse)
async def view_chambre(
    request: Request,
    chambre_id: int,
    session: Session = Depends(get_session)
):
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    lits = session.exec(select(Lit).where(Lit.chambre_id == chambre_id).order_by(Lit.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/chambre_detail.html",
        {"request": request, "chambre": chambre, "lits": lits},
    )

@router.get("/chambres/{chambre_id}/edit", response_class=HTMLResponse)
async def edit_chambre_form(
    request: Request,
    chambre_id: int,
    session: Session = Depends(get_session)
):
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/chambre_form.html",
        {
            "request": request,
            "chambre": chambre,
            "unite_hebergement": chambre.unite_hebergement,
            # Note: physical_type n'est pas fourni car une chambre est toujours de type "ro" (room)
            "status_options": get_vocabulary_options("location-status"),
            "activation_date_value": hl7_to_form_datetime(getattr(chambre, "activation_date", None)),
            "deactivation_date_value": hl7_to_form_datetime(getattr(chambre, "deactivation_date", None)),
        },
    )

@router.post("/chambres/{chambre_id}")
async def update_chambre(
    request: Request,
    chambre_id: int,
    session: Session = Depends(get_session)
):
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    form = await request.form()
    chambre.name = form.get("name", chambre.name)
    chambre.identifier = form.get("identifier", chambre.identifier)
    # Une chambre est toujours de type "ro" (room)
    chambre.physical_type = LocationPhysicalType.RO
    st = form.get("status")
    if st:
        chambre.status = LocationStatus(st)
    chambre.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    chambre.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([chambre])
    session.add(chambre)
    session.commit()
    return RedirectResponse(url=f"/structure/uh/{chambre.unite_hebergement_id}", status_code=303)

@router.post("/chambres/{chambre_id}/delete")
async def delete_chambre(
    chambre_id: int,
    session: Session = Depends(get_session)
):
    """Supprime une chambre et redirige vers l'UH parente"""
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")
    
    # On vérifie d'abord qu'il n'y a plus de lits actifs
    lits = session.exec(
        select(Lit)
        .where(Lit.chambre_id == chambre_id)
        .where(Lit.status == "active")
    ).all()
    
    if lits:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer la chambre : des lits actifs y sont rattachés"
        )

    # Delete all lits first (active or not)
    all_lits = session.exec(
        select(Lit).where(Lit.chambre_id == chambre_id)
    ).all()
    for lit in all_lits:
        session.delete(lit)
    session.commit()

    uh_id = chambre.unite_hebergement_id
    session.delete(chambre)
    session.commit()
    return RedirectResponse(url=f"/structure/uh/{uh_id}", status_code=303)

@api_router.get("/chambres", response_model=List[ChambreRead])
async def list_chambres_api(
    response: Response,
    session: Session = Depends(get_session),
    uh_id: Optional[int] = None,
    status: Optional[LocationStatus] = None,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    query = select(Chambre)
    if uh_id:
        query = query.where(Chambre.unite_hebergement_id == uh_id)
    if status:
        query = query.where(Chambre.status == status)
    chambres = _execute_paginated(
        session,
        response,
        query,
        order_by=(Chambre.name, Chambre.id),
        skip=skip,
        limit=limit,
    )
    if apply_scheduled_status(chambres):
        session.commit()
    return chambres

@api_router.get("/chambres/{chambre_id}")
def get_chambre_api(
    chambre_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant une chambre avec ses valeurs effectives"""
    chambre = session.get(Chambre, chambre_id)
    if not chambre:
        raise HTTPException(status_code=404, detail="Chambre non trouvée")

    # Retourner les données avec valeurs effectives
    return {
        "id": chambre.id,
        "identifier": chambre.identifier,
        "name": chambre.name,
        "description": chambre.description,
        "type_chambre": chambre.type_chambre,
        "gender_usage": chambre.gender_usage,
        "max_occupancy": chambre.max_occupancy,

        # Valeurs locales
        "local_operational_status": chambre.operational_status,
        "local_status": chambre.status,
        "local_mode": chambre.mode,
        "local_physical_type": chambre.physical_type,
        "local_etage": chambre.etage,
        "local_aile": chambre.aile,
        "local_opening_date": chambre.opening_date,
        "local_activation_date": chambre.activation_date,
        "local_closing_date": chambre.closing_date,
        "local_deactivation_date": chambre.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": chambre.get_effective_operational_status(),
        "effective_status": chambre.get_effective_status(),
        "effective_mode": chambre.get_effective_mode(),
        "effective_physical_type": chambre.get_effective_physical_type(),
        "effective_etage": chambre.get_effective_etage(),
        "effective_aile": chambre.get_effective_aile(),
        "effective_opening_date": chambre.get_effective_opening_date(),
        "effective_activation_date": chambre.get_effective_activation_date(),
        "effective_closing_date": chambre.get_effective_closing_date(),
        "effective_deactivation_date": chambre.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": chambre.operational_status != chambre.get_effective_operational_status() and chambre.get_effective_operational_status() is not None,
            "status_inherited": chambre.status != chambre.get_effective_status() and chambre.get_effective_status() is not None,
            "mode_inherited": chambre.mode != chambre.get_effective_mode() and chambre.get_effective_mode() is not None,
            "physical_type_inherited": chambre.physical_type != chambre.get_effective_physical_type() and chambre.get_effective_physical_type() is not None,
            "etage_inherited": chambre.etage != chambre.get_effective_etage() and chambre.get_effective_etage() is not None,
            "aile_inherited": chambre.aile != chambre.get_effective_aile() and chambre.get_effective_aile() is not None,
            "opening_date_inherited": chambre.opening_date != chambre.get_effective_opening_date() and chambre.get_effective_opening_date() is not None,
            "activation_date_inherited": chambre.activation_date != chambre.get_effective_activation_date() and chambre.get_effective_activation_date() is not None,
            "closing_date_inherited": chambre.closing_date != chambre.get_effective_closing_date() and chambre.get_effective_closing_date() is not None,
            "deactivation_date_inherited": chambre.deactivation_date != chambre.get_effective_deactivation_date() and chambre.get_effective_deactivation_date() is not None,
        },

        # Relations
        "unite_hebergement_id": chambre.unite_hebergement_id,
        "unite_hebergement": {
            "id": chambre.unite_hebergement.id,
            "name": chambre.unite_hebergement.name,
            "identifier": chambre.unite_hebergement.identifier
        } if chambre.unite_hebergement else None,

        # Statistiques
        "stats": {
            "lits_count": len(chambre.lits) if hasattr(chambre, 'lits') else 0,
        },

        # Timestamps
        "created_at": chambre.created_at,
        "updated_at": chambre.updated_at,
    }

@router.post("/chambres", response_model=Chambre)
async def create_chambre(
    request: Request,
    session: Session = Depends(get_session)
):
    form = await request.form()
    status_value = form.get("status") or LocationStatus.ACTIVE
    chambre = Chambre(
        name=form["name"],
        identifier=form["identifier"],
        unite_hebergement_id=int(form["unite_hebergement_id"]),
        physical_type=LocationPhysicalType.RO,  # Une chambre est toujours de type "ro" (room)
        mode=LocationMode(form.get("mode", LocationMode.INSTANCE)),
        status=LocationStatus(status_value),
        type_chambre=form.get("type_chambre"),
        gender_usage=form.get("gender_usage")
    )
    chambre.activation_date = form_datetime_to_hl7(form.get("activation_date"))
    chambre.deactivation_date = form_datetime_to_hl7(form.get("deactivation_date"))
    apply_scheduled_status([chambre])
    session.add(chambre)
    session.commit()
    session.refresh(chambre)
    
    # Rediriger vers la vue de l'UH parente
    return RedirectResponse(
        url=f"/structure/uh/{chambre.unite_hebergement_id}",
        status_code=303
    )

# --- Lits ---
@router.get("/lits", response_class=HTMLResponse)
async def list_lits(
    request: Request,
    session: Session = Depends(get_session),
    chambre_id: Optional[int] = Query(None),
    status: Optional[LocationStatus] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Lit)
    if chambre_id:
        query = query.where(Lit.chambre_id == chambre_id)
    if status:
        query = query.where(Lit.status == status)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Lit.name.ilike(like))
            | (Lit.identifier.ilike(like))
        )
    
    lits = session.exec(query.order_by(Lit.name)).all()
    if apply_scheduled_status(lits):
        session.commit()
    
    chambres = session.exec(select(Chambre).order_by(Chambre.name)).all()
    chambre_map = {chambre.id: chambre.name for chambre in chambres}
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/lits_list.html",
        {
            "request": request,
            "lits": lits,
            "chambres": chambres,
            "chambre_map": chambre_map,
            "statuses": LocationStatus,
            "selected_chambre_id": chambre_id,
            "selected_status": status.value if status else None,
            "search_term": q,
        },
    )

@router.get("/api/lits", response_model=List[LitRead])
async def list_lits_api(
    response: Response,
    session: Session = Depends(get_session),
    chambre_id: Optional[int] = None,
    status: Optional[LocationStatus] = None,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    query = select(Lit)
    if chambre_id:
        query = query.where(Lit.chambre_id == chambre_id)
    if status:
        query = query.where(Lit.status == status)
    lits = _execute_paginated(
        session,
        response,
        query,
        order_by=(Lit.name, Lit.id),
        skip=skip,
        limit=limit,
    )
    if apply_scheduled_status(lits):
        session.commit()
    return lits

@api_router.get("/lits/{lit_id}")
def get_lit_api(
    lit_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant un lit avec ses valeurs effectives"""
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")

    # Retourner les données avec valeurs effectives
    return {
        "id": lit.id,
        "identifier": lit.identifier,
        "name": lit.name,
        "description": lit.description,
        "max_occupancy": lit.max_occupancy,

        # Valeurs locales
        "local_operational_status": lit.operational_status,
        "local_status": lit.status,
        "local_mode": lit.mode,
        "local_physical_type": lit.physical_type,
        "local_etage": lit.etage,
        "local_aile": lit.aile,
        "local_opening_date": lit.opening_date,
        "local_activation_date": lit.activation_date,
        "local_closing_date": lit.closing_date,
        "local_deactivation_date": lit.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": lit.get_effective_operational_status(),
        "effective_status": lit.get_effective_status(),
        "effective_mode": lit.get_effective_mode(),
        "effective_physical_type": lit.get_effective_physical_type(),
        "effective_etage": lit.get_effective_etage(),
        "effective_aile": lit.get_effective_aile(),
        "effective_opening_date": lit.get_effective_opening_date(),
        "effective_activation_date": lit.get_effective_activation_date(),
        "effective_closing_date": lit.get_effective_closing_date(),
        "effective_deactivation_date": lit.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": lit.operational_status != lit.get_effective_operational_status() and lit.get_effective_operational_status() is not None,
            "status_inherited": lit.status != lit.get_effective_status() and lit.get_effective_status() is not None,
            "mode_inherited": lit.mode != lit.get_effective_mode() and lit.get_effective_mode() is not None,
            "physical_type_inherited": lit.physical_type != lit.get_effective_physical_type() and lit.get_effective_physical_type() is not None,
            "etage_inherited": lit.etage != lit.get_effective_etage() and lit.get_effective_etage() is not None,
            "aile_inherited": lit.aile != lit.get_effective_aile() and lit.get_effective_aile() is not None,
            "opening_date_inherited": lit.opening_date != lit.get_effective_opening_date() and lit.get_effective_opening_date() is not None,
            "activation_date_inherited": lit.activation_date != lit.get_effective_activation_date() and lit.get_effective_activation_date() is not None,
            "closing_date_inherited": lit.closing_date != lit.get_effective_closing_date() and lit.get_effective_closing_date() is not None,
            "deactivation_date_inherited": lit.deactivation_date != lit.get_effective_deactivation_date() and lit.get_effective_deactivation_date() is not None,
        },

        # Relations
        "chambre_id": lit.chambre_id,
        "chambre": {
            "id": lit.chambre.id,
            "name": lit.chambre.name,
            "identifier": lit.chambre.identifier
        } if lit.chambre else None,

        # Statistiques
        "stats": {},

        # Timestamps
        "created_at": lit.created_at,
        "updated_at": lit.updated_at,
    }

@router.post("/lits", response_model=Lit)
async def create_lit(
    lit: Lit,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([lit])
    session.add(lit)
    session.commit()
    session.refresh(lit)
    return lit

@router.get("/lits/{lit_id}", response_class=HTMLResponse)
async def view_lit(
    request: Request,
    lit_id: int,
    session: Session = Depends(get_session)
):
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/lit_detail.html",
        {"request": request, "lit": lit},
    )

@router.get("/lits/{lit_id}/edit", response_class=HTMLResponse)
async def edit_lit_form(
    request: Request,
    lit_id: int,
    session: Session = Depends(get_session)
):
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    chambres = session.exec(select(Chambre).order_by(Chambre.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/lit_form.html",
        {
            "request": request,
            "lit": lit,
            "chambres": chambres,
            "status_options": get_vocabulary_options("location-status"),
            "operational_statuses": LIT_OPERATIONAL_STATUS_OPTIONS,
        },
    )

@router.post("/lits/{lit_id}")
async def update_lit(
    lit_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    chambre_id: Optional[int] = Form(None),
    status: Optional[str] = Form(None),
    operational_status: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    lit = session.get(Lit, lit_id)
    if not lit:
        raise HTTPException(status_code=404, detail="Lit non trouvé")
    lit.name = name
    if identifier is not None:
        lit.identifier = identifier
    if chambre_id:
        lit.chambre_id = int(chambre_id)
    if status:
        lit.status = LocationStatus(status)
    if operational_status is not None:
        lit.operational_status = operational_status
    # Un lit est toujours de type "bd" (bed)
    lit.physical_type = LocationPhysicalType.BD
    apply_scheduled_status([lit])
    session.add(lit)
    session.commit()
    return RedirectResponse(url=f"/structure/chambres/{lit.chambre_id}", status_code=303)
