"""
Router pour le module Analytics (Mode Gestionnaire)
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from typing import Optional
from datetime import date, datetime, timedelta
import random

from app.db import get_session
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
    Calcule les KPIs principaux pour le mode gestionnaire.
    
    **Note** : Pour le MVP, les données d'occupation sont simulées aléatoirement.
    L'intégration avec le module Mouvements se fera en Phase 3.2.
    """
    # Récupérer tous les lits (ou par EG si spécifié)
    query = select(Lit)
    if eg_id:
        # Filtrer les lits appartenant à l'entité géographique via la hiérarchie
        # Lit -> Chambre -> UniteHebergement -> UniteFonctionnelle -> Service -> Pole -> EntiteGeographique
        query = (
            query
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .join(UniteFonctionnelle, UniteFonctionnelle.id == UniteHebergement.unite_fonctionnelle_id)
            .join(Service, Service.id == UniteFonctionnelle.service_id)
            .join(Pole, Pole.id == Service.pole_id)
            .where(Pole.entite_geo_id == eg_id)
        )

    lits = session.exec(query).all()
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
    
    # Simuler occupation (65-85% en moyenne)
    occupied_beds = int(total_beds * random.uniform(0.65, 0.85))
    available_beds = total_beds - occupied_beds
    occupation_rate = (occupied_beds / total_beds) * 100
    
    # Simuler DMS (Durée Moyenne de Séjour) : 5-12 jours en moyenne
    dms = random.uniform(5.0, 12.0)
    
    # Simuler taux de rotation (admissions / lits) : 0.8-1.5
    rotation_rate = random.uniform(0.8, 1.5)
    
    # Simuler trend (évolution vs période précédente) : -5% à +5%
    occupation_trend = random.uniform(-5.0, 5.0)
    dms_trend = random.uniform(-3.0, 3.0)
    rotation_trend = random.uniform(-2.0, 2.0)
    
    # Taux d'ouverture : 100% pour MVP (tous les lits installés sont ouverts)
    beds_opening_rate = 100.0
    
    return KpiResponse(
        occupation_rate=round(occupation_rate, 1),
        occupation_trend=round(occupation_trend, 1),
        dms=round(dms, 1),
        dms_trend=round(dms_trend, 1),
        rotation_rate=round(rotation_rate, 2),
        rotation_trend=round(rotation_trend, 2),
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
    
    results = []
    for service in services:
        # Compter les lits du service via la hiérarchie
        # Lit -> Chambre -> UniteHebergement -> UniteFonctionnelle (filtrée par service)
        lits_query = (
            select(func.count(Lit.id))
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .join(UniteFonctionnelle, UniteFonctionnelle.id == UniteHebergement.unite_fonctionnelle_id)
            .where(UniteFonctionnelle.service_id == service.id)
        )
        total_beds = session.exec(lits_query).one()
        
        if total_beds == 0:
            continue
        
        # Simuler occupation (variance par service : 50-95%)
        occupied_beds = int(total_beds * random.uniform(0.50, 0.95))
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
            service_code=service.code_court,
            total_beds=total_beds,
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
    
    # Grouper par code_um
    um_stats = {}
    for uf in ufs:
        code_um = uf.um_code or "MCO"  # Default MCO si non défini

        # Compter les lits de l'UF via la hiérarchie
        # Lit -> Chambre -> UniteHebergement -> UniteFonctionnelle (filtrée par UF)
        lits_query = (
            select(func.count(Lit.id))
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .where(UniteHebergement.unite_fonctionnelle_id == uf.id)
        )
        total_beds = session.exec(lits_query).one()
        
        if total_beds == 0:
            continue
        
        if code_um not in um_stats:
            um_stats[code_um] = {"total": 0, "occupied": 0}
        
        um_stats[code_um]["total"] += total_beds
        # Simuler occupation
        um_stats[code_um]["occupied"] += int(total_beds * random.uniform(0.60, 0.85))
    
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
    
    for service in services:
        # Compter les lits du service via la hiérarchie
        lits_query = (
            select(func.count(Lit.id))
            .join(Chambre, Chambre.id == Lit.chambre_id)
            .join(UniteHebergement, UniteHebergement.id == Chambre.unite_hebergement_id)
            .join(UniteFonctionnelle, UniteFonctionnelle.id == UniteHebergement.unite_fonctionnelle_id)
            .where(UniteFonctionnelle.service_id == service.id)
        )
        total_beds = session.exec(lits_query).one()
        
        if total_beds == 0:
            continue
        
        occupied_beds = int(total_beds * random.uniform(0.50, 1.05))  # Peut dépasser 100% (suroccupation)
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
