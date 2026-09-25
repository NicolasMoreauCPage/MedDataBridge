"""Recherche de disponibilité dans la structure hospitalière."""
import logging
from typing import Optional

from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.db import get_session
from app.services.structure_schedule import apply_scheduled_status
from app.models_structure import (
    Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit,
    LocationStatus, LocationServiceType,
)
from app.routers.structure_router_base import (
    get_templates_with_filters,
    router,
)

logger = logging.getLogger(__name__)

@router.get("/availability", response_class=HTMLResponse)
def structure_availability_search(
    request: Request,
    session: Session = Depends(get_session),
    service_type: Optional[LocationServiceType] = Query(None),
    uf_id: Optional[int] = Query(None),
):
    services = session.exec(select(Service).order_by(Service.name)).all()
    apply_scheduled_status(services)

    service_ids = [svc.id for svc in services if not service_type or svc.service_type == service_type]
    available_ufs_query = select(UniteFonctionnelle).order_by(UniteFonctionnelle.name)
    if service_type:
        if service_ids:
            available_ufs_query = available_ufs_query.where(UniteFonctionnelle.service_id.in_(service_ids))
        else:
            available_ufs_query = available_ufs_query.where(False)
    ufs = session.exec(available_ufs_query).all()
    apply_scheduled_status(ufs)

    results = []
    if service_type or uf_id:
        lits = _fetch_available_lits(session, service_type=service_type, uf_id=uf_id)
        for lit in lits:
            chambre = lit.chambre
            uh = chambre.unite_hebergement if chambre else None
            uf = uh.unite_fonctionnelle if uh else None
            service = uf.service if uf else None
            pole = service.pole if service else None
            eg = pole.entite_geo if pole else None
            results.append(
                {
                    "lit": lit,
                    "chambre": chambre,
                    "uh": uh,
                    "uf": uf,
                    "service": service,
                    "pole": pole,
                    "entite_geo": eg,
                }
            )

    return get_templates_with_filters(request).TemplateResponse(
        request,
        "structure/search.html",
        {
            "request": request,
            "service_types": [stype for stype in LocationServiceType],
            "services": services,
            "unites_fonctionnelles": ufs,
            "selected_service_type": service_type.value if service_type else None,
            "selected_uf_id": uf_id,
            "results": results,
        },
    )

# --- Utilitaires de recherche ---
def _fetch_available_lits(
    session: Session,
    service_type: Optional[LocationServiceType] = None,
    uf_id: Optional[int] = None,
):
    """Return lits libres en tenant compte des programmations."""
    query = (
        select(Lit)
        .options(
            selectinload(Lit.chambre)
            .selectinload(Chambre.unite_hebergement)
            .selectinload(UniteHebergement.unite_fonctionnelle)
            .selectinload(UniteFonctionnelle.service)
            .selectinload(Service.pole)
            .selectinload(Pole.entite_geo)
        )
        .join(Chambre)
        .join(UniteHebergement)
        .join(UniteFonctionnelle)
        .join(Service)
        .where(Lit.operationalStatus == "libre")
    )
    if service_type:
        query = query.where(Service.service_type == service_type)
    if uf_id:
        query = query.where(UniteFonctionnelle.id == uf_id)

    lits = session.exec(query).scalars().all()
    apply_scheduled_status(lits)
    for lit in lits:
        if lit.chambre:
            apply_scheduled_status([lit.chambre])
        uh = getattr(lit.chambre, "unite_hebergement", None)
        if uh:
            apply_scheduled_status([uh])
        uf = getattr(uh, "unite_fonctionnelle", None) if uh else None
        if uf:
            apply_scheduled_status([uf])
        service = getattr(uf, "service", None) if uf else None
        if service:
            apply_scheduled_status([service])
        pole = getattr(service, "pole", None) if service else None
        if pole:
            apply_scheduled_status([pole])
        eg = getattr(pole, "entite_geo", None) if pole else None
        if eg:
            apply_scheduled_status([eg])
    # Filtrer les lits actifs après application
    return [lit for lit in lits if lit.status == LocationStatus.ACTIVE]


@router.get("/search/lits-disponibles")
def search_lits_disponibles(
    session: Session = Depends(get_session),
    service_type: Optional[LocationServiceType] = None,
    uf_id: Optional[int] = None,
):
    """Recherche les lits disponibles avec filtres (JSON)."""
    return _fetch_available_lits(session, service_type=service_type, uf_id=uf_id)
