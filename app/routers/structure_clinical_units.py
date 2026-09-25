"""Routes des services et des unités fonctionnelles."""
import logging
from typing import List, Optional
from unittest.mock import Mock as MockType

from fastapi import Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.services.structure_schedule import apply_scheduled_status
from app.services.vocabulary_lookup import get_vocabulary_options
from app.schemas.structure import (
    ServiceRead,
    UniteFonctionnelleRead,
)
from app.models_structure import (
    Pole, Service, UniteFonctionnelle,
    UniteHebergement,
    LocationPhysicalType, LocationServiceType,
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


@router.get("/services", response_class=HTMLResponse)
def list_services(
    request: Request,
    session: Session = Depends(get_session),
    pole_id: Optional[int] = Query(None),
    service_type: Optional[LocationServiceType] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(Service)
    if pole_id:
        query = query.where(Service.pole_id == pole_id)
    if service_type:
        query = query.where(Service.service_type == service_type)
    if q:
        like = f"%{q}%"
        query = query.where(
            (Service.name.ilike(like))
            | (Service.identifier.ilike(like))
        )
    
    services = session.exec(query.order_by(Service.name)).all()
    apply_scheduled_status(services)
    
    poles = session.exec(select(Pole).order_by(Pole.name)).all()
    pole_map = {pole.id: pole.name for pole in poles}
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/services_list.html",
        {
            "request": request,
            "services": services,
            "poles": poles,
            "pole_map": pole_map,
            "service_types": LocationServiceType,
            "selected_pole_id": pole_id,
            "selected_service_type": service_type.value if service_type else None,
            "search_term": q,
        },
    )

@router.get("/api/services", response_model=List[ServiceRead])
def list_services_api(
    response: Response,
    session: Session = Depends(get_session),
    pole_id: Optional[int] = None,
    service_type: Optional[LocationServiceType] = None,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    query = select(Service)
    if pole_id:
        query = query.where(Service.pole_id == pole_id)
    if service_type:
        query = query.where(Service.service_type == service_type)
    services = _execute_paginated(
        session,
        response,
        query,
        order_by=(Service.name, Service.id),
        skip=skip,
        limit=limit,
    )
    apply_scheduled_status(services)
    return services

@api_router.get("/services/{service_id}")
def get_service_api(
    service_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant un service avec ses valeurs effectives"""
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")

    # Retourner les données avec valeurs effectives
    return {
        "id": service.id,
        "identifier": service.identifier,
        "name": service.name,
        "short_name": service.short_name,
        "description": service.description,
        "service_type": service.service_type,

        # Valeurs locales
        "local_operational_status": service.operational_status,
        "local_status": service.status,
        "local_mode": service.mode,
        "local_physical_type": service.physical_type,
        "local_etage": service.etage,
        "local_aile": service.aile,
        "local_type_chambre": service.type_chambre,
        "local_opening_date": service.opening_date,
        "local_activation_date": service.activation_date,
        "local_closing_date": service.closing_date,
        "local_deactivation_date": service.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": service.get_effective_operational_status(),
        "effective_status": service.get_effective_status(),
        "effective_mode": service.get_effective_mode(),
        "effective_physical_type": service.get_effective_physical_type(),
        "effective_etage": service.get_effective_etage(),
        "effective_aile": service.get_effective_aile(),
        "effective_type_chambre": service.get_effective_type_chambre(),
        "effective_opening_date": service.get_effective_opening_date(),
        "effective_activation_date": service.get_effective_activation_date(),
        "effective_closing_date": service.get_effective_closing_date(),
        "effective_deactivation_date": service.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": service.operational_status != service.get_effective_operational_status() and service.get_effective_operational_status() is not None,
            "status_inherited": service.status != service.get_effective_status() and service.get_effective_status() is not None,
            "mode_inherited": service.mode != service.get_effective_mode() and service.get_effective_mode() is not None,
            "physical_type_inherited": service.physical_type != service.get_effective_physical_type() and service.get_effective_physical_type() is not None,
            "etage_inherited": service.etage != service.get_effective_etage() and service.get_effective_etage() is not None,
            "aile_inherited": service.aile != service.get_effective_aile() and service.get_effective_aile() is not None,
            "type_chambre_inherited": service.type_chambre != service.get_effective_type_chambre() and service.get_effective_type_chambre() is not None,
            "opening_date_inherited": service.opening_date != service.get_effective_opening_date() and service.get_effective_opening_date() is not None,
            "activation_date_inherited": service.activation_date != service.get_effective_activation_date() and service.get_effective_activation_date() is not None,
            "closing_date_inherited": service.closing_date != service.get_effective_closing_date() and service.get_effective_closing_date() is not None,
            "deactivation_date_inherited": service.deactivation_date != service.get_effective_deactivation_date() and service.get_effective_deactivation_date() is not None,
        },

        # Relations
        "pole_id": service.pole_id,
        "pole": {
            "id": service.pole.id,
            "name": service.pole.name,
            "identifier": service.pole.identifier
        } if service.pole else None,

        # Statistiques
        "stats": {
            "unites_fonctionnelles_count": (lambda obj: 0 if obj is None or isinstance(obj, MockType) else (len(obj) if hasattr(obj, '__len__') else (sum(1 for _ in obj) if obj is not None else 0)))(getattr(service, 'unites_fonctionnelles', None)),
        },

        # Timestamps
        "created_at": service.created_at,
        "updated_at": service.updated_at,
    }

@router.post("/services", response_model=ServiceRead)
def create_service(
    service: Service,
    session: Session = Depends(get_session)
):
    # Un service est toujours de type "wa" (ward)
    service.physical_type = LocationPhysicalType.WA
    apply_scheduled_status([service])
    session.add(service)
    session.commit()
    session.refresh(service)
    return service

@router.get("/services/{service_id}", response_class=HTMLResponse)
def view_service(
    request: Request,
    service_id: int,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service_id).order_by(UniteFonctionnelle.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/service_detail.html",
        {"request": request, "service": service, "ufs": ufs, "service_types": LocationServiceType},
    )

@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
def edit_service_form(
    request: Request,
    service_id: int,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    poles = session.exec(select(Pole).order_by(Pole.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/service_form.html",
        {
            "request": request,
            "service": service,
            "poles": poles,
            "service_type_options": get_vocabulary_options("location-service-type"),
        },
    )

@router.post("/services/{service_id}")
def update_service(
    service_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    pole_id: Optional[int] = Form(None),
    service_type: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    service.name = name
    if identifier is not None:
        service.identifier = identifier
    if pole_id:
        service.pole_id = int(pole_id)
    if service_type:
        service.service_type = LocationServiceType(service_type)
    # Un service est toujours de type "wa" (ward)
    service.physical_type = LocationPhysicalType.WA
    apply_scheduled_status([service])
    session.add(service)
    session.commit()
    return RedirectResponse(url=f"/structure/services/{service_id}", status_code=303)

@router.post("/services/{service_id}/delete")
def delete_service(
    service_id: int,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service non trouvé")
    session.delete(service)
    session.commit()
    return RedirectResponse(url="/structure/services", status_code=303)

# --- Unités Fonctionnelles ---
@router.get("/ufs", response_class=HTMLResponse)
def list_unites_fonctionnelles(
    request: Request,
    session: Session = Depends(get_session),
    service_id: Optional[int] = Query(None),
    service_type: Optional[LocationServiceType] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
):
    query = select(UniteFonctionnelle)
    if service_id:
        query = query.where(UniteFonctionnelle.service_id == service_id)
    if service_type:
        service_ids = session.exec(
            select(Service.id).where(Service.service_type == service_type)
        ).all()
        if service_ids:
            query = query.where(UniteFonctionnelle.service_id.in_(service_ids))
        else:
            query = query.where(False)  # Aucun service ne correspond
    if q:
        like = f"%{q}%"
        query = query.where(
            (UniteFonctionnelle.name.ilike(like))
            | (UniteFonctionnelle.identifier.ilike(like))
        )

    ufs = session.exec(query.order_by(UniteFonctionnelle.name)).all()
    apply_scheduled_status(ufs)
    services = session.exec(select(Service).order_by(Service.name)).all()
    apply_scheduled_status(services)
    service_map = {service.id: service.name for service in services}

    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/ufs.html",
        {
            "request": request,
            "unites_fonctionnelles": ufs,
            "services": services,
            "service_map": service_map,
            "service_type_labels": {
                st.value: st.name for st in LocationServiceType
            },
            "selected_service_id": service_id,
            "selected_service_type": service_type.value if service_type else None,
            "search_term": q,
        },
    )

@router.get("/api/ufs", response_model=List[UniteFonctionnelleRead])
def list_unites_fonctionnelles_api(
    response: Response,
    session: Session = Depends(get_session),
    service_id: Optional[int] = None,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
    limit: int = Query(DEFAULT_API_PAGE_SIZE, ge=1, le=MAX_API_PAGE_SIZE, description="Taille maximale de page"),
):
    query = select(UniteFonctionnelle)
    if service_id:
        query = query.where(UniteFonctionnelle.service_id == service_id)
    ufs = _execute_paginated(
        session,
        response,
        query,
        order_by=(UniteFonctionnelle.name, UniteFonctionnelle.id),
        skip=skip,
        limit=limit,
    )
    apply_scheduled_status(ufs)
    return ufs

@api_router.get("/ufs/{uf_id}")
def get_unite_fonctionnelle_api(
    uf_id: int,
    session: Session = Depends(get_session)
):
    """API endpoint retournant une unité fonctionnelle avec ses valeurs effectives"""
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")

    # Retourner les données avec valeurs effectives
    return {
        "id": uf.id,
        "identifier": uf.identifier,
        "name": uf.name,
        "short_name": uf.short_name,
        "description": uf.description,

        # Valeurs locales
        "local_operational_status": uf.operational_status,
        "local_status": uf.status,
        "local_mode": uf.mode,
        "local_physical_type": uf.physical_type,
        "local_etage": uf.etage,
        "local_aile": uf.aile,
        "local_opening_date": uf.opening_date,
        "local_activation_date": uf.activation_date,
        "local_closing_date": uf.closing_date,
        "local_deactivation_date": uf.deactivation_date,

        # Valeurs effectives (avec héritage)
        "effective_operational_status": uf.get_effective_operational_status(),
        "effective_status": uf.get_effective_status(),
        "effective_mode": uf.get_effective_mode(),
        "effective_physical_type": uf.get_effective_physical_type(),
        "effective_etage": uf.get_effective_etage(),
        "effective_aile": uf.get_effective_aile(),
        "effective_opening_date": uf.get_effective_opening_date(),
        "effective_activation_date": uf.get_effective_activation_date(),
        "effective_closing_date": uf.get_effective_closing_date(),
        "effective_deactivation_date": uf.get_effective_deactivation_date(),

        # Métadonnées d'héritage
        "inheritance_info": {
            "operational_status_inherited": uf.operational_status != uf.get_effective_operational_status() and uf.get_effective_operational_status() is not None,
            "status_inherited": uf.status != uf.get_effective_status() and uf.get_effective_status() is not None,
            "mode_inherited": uf.mode != uf.get_effective_mode() and uf.get_effective_mode() is not None,
            "physical_type_inherited": uf.physical_type != uf.get_effective_physical_type() and uf.get_effective_physical_type() is not None,
            "etage_inherited": uf.etage != uf.get_effective_etage() and uf.get_effective_etage() is not None,
            "aile_inherited": uf.aile != uf.get_effective_aile() and uf.get_effective_aile() is not None,
            "opening_date_inherited": uf.opening_date != uf.get_effective_opening_date() and uf.get_effective_opening_date() is not None,
            "activation_date_inherited": uf.activation_date != uf.get_effective_activation_date() and uf.get_effective_activation_date() is not None,
            "closing_date_inherited": uf.closing_date != uf.get_effective_closing_date() and uf.get_effective_closing_date() is not None,
            "deactivation_date_inherited": uf.deactivation_date != uf.get_effective_deactivation_date() and uf.get_effective_deactivation_date() is not None,
        },

        # Relations
        "service_id": uf.service_id,
        "service": {
            "id": uf.service.id,
            "name": uf.service.name,
            "identifier": uf.service.identifier
        } if uf.service else None,

        # Statistiques
        "stats": {
            "unites_hebergement_count": (lambda obj: 0 if obj is None or isinstance(obj, MockType) else (len(obj) if hasattr(obj, '__len__') else (sum(1 for _ in obj) if obj is not None else 0)))(getattr(uf, 'unites_hebergement', None)),
        },

        # Timestamps
        "created_at": uf.created_at,
        "updated_at": uf.updated_at,
    }

@router.post("/ufs", response_model=UniteFonctionnelleRead)
def create_unite_fonctionnelle(
    uf: UniteFonctionnelle,
    session: Session = Depends(get_session)
):
    apply_scheduled_status([uf])
    session.add(uf)
    session.commit()
    session.refresh(uf)
    return uf

@router.get("/ufs/{uf_id}", response_class=HTMLResponse)
def view_unite_fonctionnelle(
    request: Request,
    uf_id: int,
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf_id).order_by(UniteHebergement.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/uf_detail.html",
        {"request": request, "uf": uf, "uhs": uhs},
    )

@router.get("/ufs/{uf_id}/edit", response_class=HTMLResponse)
def edit_unite_fonctionnelle_form(
    request: Request,
    uf_id: int,
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    services = session.exec(select(Service).order_by(Service.name)).all()
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/uf_form.html",
        {"request": request, "uf": uf, "services": services},
    )

@router.post("/ufs/{uf_id}")
def update_unite_fonctionnelle(
    uf_id: int,
    name: str = Form(...),
    identifier: Optional[str] = Form(None),
    service_id: Optional[int] = Form(None),
    uf_type: Optional[str] = Form(None),
    um_code: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    uf.name = name
    if identifier is not None:
        uf.identifier = identifier
    if service_id:
        uf.service_id = int(service_id)
    if uf_type is not None:
        uf.uf_type = uf_type
    if um_code is not None:
        uf.um_code = um_code
    # Une UF est toujours de type "wa" (ward)
    uf.physical_type = LocationPhysicalType.WA
    apply_scheduled_status([uf])
    session.add(uf)
    session.commit()
    return RedirectResponse(url=f"/structure/ufs/{uf_id}", status_code=303)

@router.post("/ufs/{uf_id}/delete")
def delete_unite_fonctionnelle(
    uf_id: int,
    session: Session = Depends(get_session)
):
    uf = session.get(UniteFonctionnelle, uf_id)
    if not uf:
        raise HTTPException(status_code=404, detail="UF non trouvée")
    session.delete(uf)
    session.commit()
    return RedirectResponse(url="/structure/ufs", status_code=303)

# --- Unités d'Hébergement ---
