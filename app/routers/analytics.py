"""
Router pour le module Analytics (Mode Gestionnaire)
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from typing import Optional
from datetime import date, datetime, timedelta

from app.db import get_session
from app.models import Dossier, Venue
from app.models_structure import (
    Lit,
    UniteFonctionnelle,
    Service,
    Pole,
    EntiteGeographique,
    Chambre,
    UniteHebergement,
)
from app.models_analytics import (
    KpiResponse,
    CapacityByServiceResponse,
    CapacityByUmResponse,
    ComputedAlert,
    AlertType,
    AlertSeverity,
    OccupationSnapshot,
    AlertRule
)
from app.services.structure_validation import get_occupied_lit_ids

_PERIOD_DAYS = {"7d": 7, "30d": 30, "1y": 365}


def _lits_query_for_eg(eg_id: Optional[int]):
    """Requête des lits, filtrée par EG via la hiérarchie de structure si `eg_id` est fourni."""
    query = select(Lit)
    if eg_id:
        query = (
            query
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .join(UniteFonctionnelle, UniteFonctionnelle.id == UniteHebergement.unite_fonctionnelle_id)
            .join(Service, Service.id == UniteFonctionnelle.service_id)
            .join(Pole, Pole.id == Service.pole_id)
            .where(Pole.entite_geo_id == eg_id)
        )
    return query


def _dossiers_in_scope(session: Session, lit_ids: Optional[set]):
    """Dossiers dont au moins un Venue est rattaché à un lit du périmètre (ou tous si pas de périmètre)."""
    query = select(Dossier)
    if lit_ids is not None:
        query = query.join(Venue, Venue.dossier_id == Dossier.id).where(Venue.lit_id.in_(lit_ids)).distinct()
    return session.exec(query).all()


def _compute_dms(dossiers: list) -> float:
    """Durée Moyenne de Séjour (jours) sur les dossiers déjà sortis."""
    durations = [
        (d.discharge_time - d.admit_time).total_seconds() / 86400
        for d in dossiers
        if d.discharge_time and d.admit_time
    ]
    return sum(durations) / len(durations) if durations else 0.0

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Router pour les pages HTML (sans prefix /api)
ui_router = APIRouter(prefix="/structure", tags=["analytics-ui"])
templates = Jinja2Templates(directory="app/templates")


@ui_router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    eg_id: Optional[int] = Query(None, description="ID de l'Entité Géographique"),
    session: Session = Depends(get_session)
):
    """Page du dashboard analytics (Mode Gestionnaire)"""
    # Si pas d'EG spécifié, prendre le premier disponible
    if not eg_id:
        first_eg = session.exec(select(EntiteGeographique)).first()
        eg_id = first_eg.id if first_eg else None
    
    return templates.TemplateResponse("analytics_dashboard.html", {
        "request": request,
        "eg_id": eg_id
    })


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(
    eg_id: Optional[int] = Query(None, description="ID de l'Entité Géographique"),
    period: str = Query("7d", description="Période: 7d, 30d, 1y"),
    session: Session = Depends(get_session)
):
    """
    Calcule les KPIs principaux pour le mode gestionnaire, à partir des données réelles
    d'admission/sortie (Dossier/Venue) plutôt que d'une simulation aléatoire.
    """
    lits = session.exec(_lits_query_for_eg(eg_id)).all()
    total_beds = len(lits)

    if total_beds == 0:
        return KpiResponse(
            occupation_rate=0.0,
            dms=0.0,
            rotation_rate=0.0,
            available_beds=0,
            total_beds=0,
            beds_opening_rate=100.0,
            period=period
        )

    lit_ids = {l.id for l in lits}
    occupied_lit_ids = get_occupied_lit_ids(session)
    occupied_beds = len(lit_ids & occupied_lit_ids)
    available_beds = total_beds - occupied_beds
    occupation_rate = (occupied_beds / total_beds) * 100

    days = _PERIOD_DAYS.get(period, 7)
    now = datetime.now()
    period_start = now - timedelta(days=days)
    previous_period_start = now - timedelta(days=2 * days)

    dossiers_in_scope = _dossiers_in_scope(session, lit_ids if eg_id else None)

    current_discharged = [d for d in dossiers_in_scope if d.discharge_time and d.discharge_time >= period_start]
    previous_discharged = [
        d for d in dossiers_in_scope
        if d.discharge_time and previous_period_start <= d.discharge_time < period_start
    ]
    dms = _compute_dms(current_discharged)
    previous_dms = _compute_dms(previous_discharged)
    dms_trend = round(dms - previous_dms, 1) if previous_discharged else None

    current_admissions = len([d for d in dossiers_in_scope if d.admit_time and d.admit_time >= period_start])
    previous_admissions = len([
        d for d in dossiers_in_scope
        if d.admit_time and previous_period_start <= d.admit_time < period_start
    ])
    rotation_rate = current_admissions / total_beds
    previous_rotation_rate = previous_admissions / total_beds
    rotation_trend = round(rotation_rate - previous_rotation_rate, 2) if previous_admissions else None

    # Taux d'ouverture : 100% par approximation assumée (pas de suivi historique
    # d'ouverture/fermeture de lit distinct du statut courant) — pas une valeur simulée
    # aléatoirement, juste une hypothèse MVP documentée.
    beds_opening_rate = 100.0

    return KpiResponse(
        occupation_rate=round(occupation_rate, 1),
        occupation_trend=None,
        dms=round(dms, 1),
        dms_trend=dms_trend,
        rotation_rate=round(rotation_rate, 2),
        rotation_trend=rotation_trend,
        available_beds=available_beds,
        total_beds=total_beds,
        beds_opening_rate=beds_opening_rate,
        period=period
    )


@router.get("/capacity-by-service", response_model=list[CapacityByServiceResponse])
def get_capacity_by_service(
    eg_id: int = Query(..., description="ID de l'Entité Géographique (requis)"),
    session: Session = Depends(get_session)
):
    """
    Retourne la capacité et l'occupation par service.
    
    Utilisé pour le graphique horizontal bar chart "Capacité par service".
    """
    # Récupérer tous les services de l'EG avec leurs lits
    services_query = (
        select(Service)
        .join(Pole, Pole.id == Service.pole_id)
        .where(Pole.entite_geo_id == eg_id)
    )
    services = session.exec(services_query).all()
    occupied_lit_ids = get_occupied_lit_ids(session)

    results = []
    for service in services:
        # Lits du service via la hiérarchie Lit -> Chambre -> UniteHebergement -> UniteFonctionnelle
        lits_query = (
            select(Lit.id)
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .join(UniteFonctionnelle, UniteFonctionnelle.id == UniteHebergement.unite_fonctionnelle_id)
            .where(UniteFonctionnelle.service_id == service.id)
        )
        service_lit_ids = set(session.exec(lits_query).all())
        total_beds = len(service_lit_ids)

        if total_beds == 0:
            continue

        occupied_beds = len(service_lit_ids & occupied_lit_ids)
        occupation_rate = (occupied_beds / total_beds) * 100
        
        # Déterminer couleur status
        if occupation_rate >= 95:
            status_color = "red"
        elif occupation_rate >= 80:
            status_color = "yellow"
        else:
            status_color = "green"
        
        results.append(CapacityByServiceResponse(
            service_id=service.id,
            service_name=service.name,
            service_code=getattr(service, 'identifier', None) or getattr(service, 'short_name', None),
            total_beds=int(total_beds),
            occupied_beds=occupied_beds,
            occupation_rate=round(occupation_rate, 1),
            status_color=status_color
        ))
    
    # Trier par taux d'occupation décroissant
    results.sort(key=lambda x: x.occupation_rate, reverse=True)
    return results


@router.get("/capacity-by-um", response_model=list[CapacityByUmResponse])
def get_capacity_by_um(
    eg_id: int = Query(..., description="ID de l'Entité Géographique (requis)"),
    session: Session = Depends(get_session)
):
    """
    Retourne la répartition de la capacité par type UM (MCO, SSR, PSY, HAD).
    
    Utilisé pour le pie chart "Répartition par Type UM".
    """
    # Mapping codes UM vers labels
    um_labels = {
        "MCO": "Médecine Chirurgie Obstétrique",
        "SSR": "Soins de Suite et Réadaptation",
        "PSY": "Psychiatrie",
        "HAD": "Hospitalisation à Domicile"
    }
    
    # Récupérer toutes les UF de l'EG avec leurs codes UM
    # EntiteGeographique -> Pole -> Service -> UniteFonctionnelle
    ufs_query = (
        select(UniteFonctionnelle)
        .join(Service, Service.id == UniteFonctionnelle.service_id)
        .join(Pole, Pole.id == Service.pole_id)
        .where(Pole.entite_geo_id == eg_id)
    )
    ufs = session.exec(ufs_query).all()
    occupied_lit_ids = get_occupied_lit_ids(session)

    # Grouper par code_um
    um_stats = {}
    for uf in ufs:
        code_um = uf.um_code or "MCO"  # Default MCO si non défini

        # Lits de l'UF via la hiérarchie Lit -> Chambre -> UniteHebergement (filtrée par UF)
        lits_query = (
            select(Lit.id)
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .where(UniteHebergement.unite_fonctionnelle_id == uf.id)
        )
        uf_lit_ids = set(session.exec(lits_query).all())
        total_beds = len(uf_lit_ids)

        if total_beds == 0:
            continue

        if code_um not in um_stats:
            um_stats[code_um] = {"total": 0, "occupied": 0}

        um_stats[code_um]["total"] += total_beds
        um_stats[code_um]["occupied"] += len(uf_lit_ids & occupied_lit_ids)
    
    results = []
    for um_code, stats in um_stats.items():
        occupation_rate = (stats["occupied"] / stats["total"]) * 100 if stats["total"] > 0 else 0.0
        
        results.append(CapacityByUmResponse(
            um_code=um_code,
            um_label=um_labels.get(um_code, um_code),
            total_beds=stats["total"],
            occupied_beds=stats["occupied"],
            occupation_rate=round(occupation_rate, 1)
        ))
    
    # Trier par capacité totale décroissante
    results.sort(key=lambda x: x.total_beds, reverse=True)
    return results


@router.get("/alerts", response_model=list[ComputedAlert])
def get_alerts(
    eg_id: int = Query(..., description="ID de l'Entité Géographique (requis)"),
    severity: Optional[str] = Query(None, description="Filtrer par sévérité: high, medium, low"),
    session: Session = Depends(get_session)
):
    """
    Génère les alertes actives en comparant les données réelles avec les règles d'alerte.
    
    Pour le MVP, on génère des alertes basiques :
    - Suroccupation > 95%
    - Tension > 90%
    - Sous-utilisation < 50%
    """
    alerts = []

    # Récupérer les services avec leur occupation
    services_data = []
    services_query = (
        select(Service)
        .join(Pole, Pole.id == Service.pole_id)
        .where(Pole.entite_geo_id == eg_id)
    )
    services = session.exec(services_query).all()
    occupied_lit_ids = get_occupied_lit_ids(session)

    for service in services:
        # Lits du service via la hiérarchie
        lits_query = (
            select(Lit.id)
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .join(UniteFonctionnelle, UniteFonctionnelle.id == UniteHebergement.unite_fonctionnelle_id)
            .where(UniteFonctionnelle.service_id == service.id)
        )
        service_lit_ids = set(session.exec(lits_query).all())
        total_beds = len(service_lit_ids)

        if total_beds == 0:
            continue

        occupied_beds = len(service_lit_ids & occupied_lit_ids)
        occupation_rate = (occupied_beds / total_beds) * 100

        services_data.append({
            "service": service,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "occupation_rate": occupation_rate
        })
    
    # Générer alertes
    for data in services_data:
        service = data["service"]
        rate = data["occupation_rate"]
        
        # Alerte suroccupation (> 100%)
        if rate > 100:
            alerts.append(ComputedAlert(
                alert_type=AlertType.SUROCCUPATION,
                severity=AlertSeverity.HIGH,
                entity_type="service",
                entity_id=service.id,
                entity_name=service.name,
                current_value=round(rate, 1),
                threshold_value=100.0,
                message=f"🚨 Suroccupation détectée : {data['occupied_beds']} lits occupés pour {data['total_beds']} disponibles"
            ))
        
        # Alerte tension (95-100%)
        elif rate >= 95:
            alerts.append(ComputedAlert(
                alert_type=AlertType.TENSION,
                severity=AlertSeverity.MEDIUM,
                entity_type="service",
                entity_id=service.id,
                entity_name=service.name,
                current_value=round(rate, 1),
                threshold_value=95.0,
                message=f"⚠️ Tension sur la capacité : {round(rate, 1)}% d'occupation"
            ))
        
        # Alerte sous-utilisation (< 50%)
        elif rate < 50:
            alerts.append(ComputedAlert(
                alert_type=AlertType.SOUS_UTILISATION,
                severity=AlertSeverity.LOW,
                entity_type="service",
                entity_id=service.id,
                entity_name=service.name,
                current_value=round(rate, 1),
                threshold_value=50.0,
                message=f"💤 Sous-utilisation : seulement {round(rate, 1)}% d'occupation"
            ))
    
    # Filtrer par sévérité si demandé
    if severity:
        alerts = [a for a in alerts if a.severity.value == severity.lower()]
    
    # Trier par sévérité (HIGH > MEDIUM > LOW) puis par taux
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: (severity_order[a.severity.value], -a.current_value))
    
    return alerts
