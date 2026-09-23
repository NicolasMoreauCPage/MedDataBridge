"""Routes des établissements géographiques et des pôles."""
import logging
from typing import List, Optional

from fastapi import Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.services.structure_schedule import apply_scheduled_status
from app.schemas.structure import (
    EntiteGeographiqueRead,
    PoleRead,
)
from app.models_structure import (
    EntiteGeographique, Pole, Service, LocationPhysicalType,
)
from app.routers.structure_router_base import (
    DEFAULT_API_PAGE_SIZE,
    MAX_API_PAGE_SIZE,
    api_router,
    execute_paginated as _execute_paginated,
    get_templates_with_filters,
    router,
)

logger = logging.getLogger(__name__)


@router.get("/eg", response_class=HTMLResponse)
def list_entites_geographiques(
    request: Request,
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(EntiteGeographique)
    
    # Filtrer par contexte EJ si présent
    if hasattr(request.state, 'ej_context') and request.state.ej_context:
        query = query.where(EntiteGeographique.entite_juridique_id == request.state.ej_context.id)
    
    if q:
        like = f"%{q}%"
        query = query.where(
            (EntiteGeographique.name.ilike(like))
            | (EntiteGeographique.identifier.ilike(like))
            | (EntiteGeographique.finess.ilike(like))
        )
    
    egs = session.exec(query.order_by(EntiteGeographique.name)).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/eg_list.html",
        {
            "request": request,
            "entites_geographiques": egs,
            "search_term": q,
        },
    )

@router.get("/api/eg", response_model=List[EntiteGeographiqueRead])
def list_entites_geographiques_api(
    response: Response,
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    return _execute_paginated(
        session,
        response,
        select(EntiteGeographique),
        order_by=(EntiteGeographique.name, EntiteGeographique.id),
        skip=skip,
        limit=limit,
    )

@router.post("/eg", response_model=EntiteGeographiqueRead)
def create_entite_geographique(
    eg: EntiteGeographique,
    session: Session = Depends(get_session)
):
    session.add(eg)
    session.commit()
    session.refresh(eg)
    
    return eg

@router.get("/eg/{eg_id}", response_class=HTMLResponse)
def view_entite_geographique(
    request: Request,
    eg_id: int,
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    # Charger les pôles associés
    poles = session.exec(
        select(Pole).where(Pole.entite_geo_id == eg_id).order_by(Pole.name)
    ).all()
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/eg_detail.html",
        {
            "request": request,
            "eg": eg,
            "poles": poles,
        },
    )

@router.get("/eg/{eg_id}/edit", response_class=HTMLResponse)
def edit_entite_geographique_form(
    request: Request,
    eg_id: int,
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/eg_edit.html",
        {
            "request": request,
            "eg": eg,
        },
    )

@router.post("/eg/{eg_id}")
def update_entite_geographique(
    eg_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    finess: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    eg.name = name
    if identifier is not None:
        eg.identifier = identifier
    if finess is not None:
        eg.finess = finess
    # Une EG est toujours de type "si" (site)
    eg.physical_type = LocationPhysicalType.SI
    
    session.add(eg)
    session.commit()
    session.refresh(eg)
    return RedirectResponse(url=f"/structure/eg/{eg_id}", status_code=303)

@router.post("/eg/{eg_id}/delete")
def delete_entite_geographique(
    eg_id: int,
    session: Session = Depends(get_session)
):
    eg = session.get(EntiteGeographique, eg_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Entité géographique non trouvée")
    
    session.delete(eg)
    session.commit()
    return RedirectResponse(url="/structure/eg", status_code=303)

# --- Pôles ---
@router.get("/poles", response_class=HTMLResponse)
def list_poles(
    request: Request,
    session: Session = Depends(get_session),
    eg_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Pole)
    if eg_id:
        query = query.where(Pole.entite_geo_id == eg_id)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Pole.name.ilike(like))
            | (Pole.identifier.ilike(like))
        )
    
    poles = session.exec(query.order_by(Pole.name)).all()
    if apply_scheduled_status(poles):
        session.commit()
    
    egs = session.exec(select(EntiteGeographique).order_by(EntiteGeographique.name)).all()
    eg_map = {eg.id: eg.name for eg in egs}
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/poles_list.html",
        {
            "request": request,
            "poles": poles,
            "entites_geographiques": egs,
            "eg_map": eg_map,
            "selected_eg_id": eg_id,
            "search_term": q,
        },
    )

@router.get("/api/poles", response_model=List[PoleRead])
def list_poles_api(
    response: Response,
    session: Session = Depends(get_session),
    eg_id: Optional[int] = None,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    query = select(Pole)
    if eg_id:
        query = query.where(Pole.entite_geo_id == eg_id)
    poles = _execute_paginated(
        session,
        response,
        query,
        order_by=(Pole.name, Pole.id),
        skip=skip,
        limit=limit,
    )
    if apply_scheduled_status(poles):
        session.commit()
    return poles

@api_router.get("/poles/{pole_id}")
def get_pole_api(
    pole_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant un pôle avec ses valeurs effectives"""
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")

    # Retourner les données avec valeurs effectives
    return {
        "id": pole.id,
        "identifier": pole.identifier,
        "name": pole.name,
        "short_name": pole.short_name,
        "description": pole.description,

        # Valeurs locales
        "local_operational_status": pole.operational_status,
        "local_status": pole.status,
        "local_mode": pole.mode,
        "local_physical_type": pole.physical_type,
        "local_etage": pole.etage,
        "local_aile": pole.aile,
        "local_opening_date": pole.opening_date,
        "local_activation_date": pole.activation_date,
        "local_closing_date": pole.closing_date,
        "local_deactivation_date": pole.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": pole.get_effective_operational_status(),
        "effective_status": pole.get_effective_status(),
        "effective_mode": pole.get_effective_mode(),
        "effective_physical_type": pole.get_effective_physical_type(),
        "effective_etage": pole.get_effective_etage(),
        "effective_aile": pole.get_effective_aile(),
        "effective_opening_date": pole.get_effective_opening_date(),
        "effective_activation_date": pole.get_effective_activation_date(),
        "effective_closing_date": pole.get_effective_closing_date(),
        "effective_deactivation_date": pole.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": pole.operational_status != pole.get_effective_operational_status() and pole.get_effective_operational_status() is not None,
            "status_inherited": pole.status != pole.get_effective_status() and pole.get_effective_status() is not None,
            "mode_inherited": pole.mode != pole.get_effective_mode() and pole.get_effective_mode() is not None,
            "physical_type_inherited": pole.physical_type != pole.get_effective_physical_type() and pole.get_effective_physical_type() is not None,
            "etage_inherited": pole.etage != pole.get_effective_etage() and pole.get_effective_etage() is not None,
            "aile_inherited": pole.aile != pole.get_effective_aile() and pole.get_effective_aile() is not None,
            "opening_date_inherited": pole.opening_date != pole.get_effective_opening_date() and pole.get_effective_opening_date() is not None,
            "activation_date_inherited": pole.activation_date != pole.get_effective_activation_date() and pole.get_effective_activation_date() is not None,
            "closing_date_inherited": pole.closing_date != pole.get_effective_closing_date() and pole.get_effective_closing_date() is not None,
            "deactivation_date_inherited": pole.deactivation_date != pole.get_effective_deactivation_date() and pole.get_effective_deactivation_date() is not None,
        },

        # Relations
        "entite_geo_id": pole.entite_geo_id,
        "entite_geographique": {
            "id": pole.entite_geographique.id,
            "name": pole.entite_geographique.name,
            "identifier": pole.entite_geographique.identifier
        } if pole.entite_geographique else None,

        # Statistiques
        "stats": {
            "services_count": len(pole.services) if hasattr(pole, 'services') else 0,
        },

        # Timestamps
        "created_at": pole.created_at,
        "updated_at": pole.updated_at,
    }

@router.post("/poles", response_model=PoleRead)
def create_pole(
    pole: Pole,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([pole])
    session.add(pole)
    session.commit()
    session.refresh(pole)
    return pole

@router.get("/poles/{pole_id}", response_class=HTMLResponse)
def view_pole(
    request: Request,
    pole_id: int,
    session: Session = Depends(get_session)
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    services = session.exec(select(Service).where(Service.pole_id == pole_id).order_by(Service.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/pole_detail.html",
        {"request": request, "pole": pole, "services": services},
    )

@router.get("/poles/{pole_id}/edit", response_class=HTMLResponse)
def edit_pole_form(
    request: Request,
    pole_id: int,
    session: Session = Depends(get_session)
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    egs = session.exec(select(EntiteGeographique).order_by(EntiteGeographique.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/pole_form.html",
        {"request": request, "pole": pole, "entites_geographiques": egs},
    )

@router.post("/poles/{pole_id}")
def update_pole(
    pole_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    entite_geo_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    pole.name = name
    if identifier is not None:
        pole.identifier = identifier
    if entite_geo_id:
        pole.entite_geo_id = int(entite_geo_id)
    # Un pôle est toujours de type "area" (zone)
    pole.physical_type = LocationPhysicalType.AREA
    apply_scheduled_status([pole])
    session.add(pole)
    session.commit()
    return RedirectResponse(url=f"/structure/poles/{pole_id}", status_code=303)

@router.post("/poles/{pole_id}/delete")
def delete_pole(
    pole_id: int,
    session: Session = Depends(get_session)
):
    pole = session.get(Pole, pole_id)
    if not pole:
        raise HTTPException(status_code=404, detail="Pôle non trouvé")
    session.delete(pole)
    session.commit()
    return RedirectResponse(url="/structure/poles", status_code=303)

# --- Services ---
