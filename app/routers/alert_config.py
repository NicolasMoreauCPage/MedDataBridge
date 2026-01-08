"""
Router pour la configuration des seuils d'alertes (Mode Gestionnaire)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.dependencies.db_deps import get_session
from app.models_analytics import AlertRule, AlertType, AlertSeverity

# Router API
router = APIRouter(prefix="/api/alert-config", tags=["Alert Configuration"])

# Router UI
ui_router = APIRouter(prefix="/structure/alert-config", tags=["Alert Configuration UI"])
templates = Jinja2Templates(directory="app/templates")


# ========== CRUD API Endpoints ==========

@router.get("/rules", response_model=List[dict])
async def get_alert_rules(
    eg_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    session: Session = Depends(get_session)
):
    """Récupérer toutes les règles d'alerte avec filtres optionnels"""
    query = select(AlertRule)
    
    if eg_id is not None:
        query = query.where(AlertRule.eg_id == eg_id)
    if is_active is not None:
        query = query.where(AlertRule.is_active == is_active)
    
    rules = session.exec(query).all()
    
    return [
        {
            "id": rule.id,
            "alert_type": rule.alert_type,
            "threshold_value": rule.threshold_value,
            "severity": rule.severity,
            "eg_id": rule.eg_id,
            "um_code": rule.um_code,
            "service_id": rule.service_id,
            "is_active": rule.is_active,
            "description": rule.description,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }
        for rule in rules
    ]


@router.post("/rules", status_code=201)
async def create_alert_rule(
    alert_type: AlertType,
    threshold_value: float,
    severity: AlertSeverity,
    eg_id: int,
    um_code: Optional[str] = None,
    service_id: Optional[int] = None,
    description: Optional[str] = None,
    is_active: bool = True,
    session: Session = Depends(get_session)
):
    """Créer une nouvelle règle d'alerte"""
    rule = AlertRule(
        alert_type=alert_type,
        threshold_value=threshold_value,
        severity=severity,
        eg_id=eg_id,
        um_code=um_code,
        service_id=service_id,
        description=description,
        is_active=is_active
    )
    
    session.add(rule)
    session.commit()
    session.refresh(rule)
    
    return {"id": rule.id, "message": "Règle créée avec succès"}


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    threshold_value: Optional[float] = None,
    severity: Optional[AlertSeverity] = None,
    is_active: Optional[bool] = None,
    description: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Mettre à jour une règle d'alerte existante"""
    rule = session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")
    
    if threshold_value is not None:
        rule.threshold_value = threshold_value
    if severity is not None:
        rule.severity = severity
    if is_active is not None:
        rule.is_active = is_active
    if description is not None:
        rule.description = description
    
    rule.updated_at = datetime.utcnow()
    
    session.add(rule)
    session.commit()
    session.refresh(rule)
    
    return {"message": "Règle mise à jour avec succès"}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    session: Session = Depends(get_session)
):
    """Supprimer une règle d'alerte"""
    rule = session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")
    
    session.delete(rule)
    session.commit()
    
    return {"message": "Règle supprimée avec succès"}


@router.post("/rules/init-defaults")
async def init_default_rules(
    eg_id: int,
    session: Session = Depends(get_session)
):
    """Initialiser les règles par défaut pour une EG si elle n'a pas de règles"""
    # Vérifier si des règles existent déjà
    existing = session.exec(
        select(AlertRule).where(AlertRule.eg_id == eg_id)
    ).first()
    
    if existing:
        return {"message": "Des règles existent déjà pour cette EG"}
    
    # Créer les règles par défaut
    default_rules = [
        AlertRule(
            alert_type=AlertType.SUROCCUPATION,
            threshold_value=100.0,
            severity=AlertSeverity.HIGH,
            eg_id=eg_id,
            description="Suroccupation > 100% (lits supplémentaires)",
            is_active=True
        ),
        AlertRule(
            alert_type=AlertType.TENSION,
            threshold_value=95.0,
            severity=AlertSeverity.MEDIUM,
            eg_id=eg_id,
            description="Tension capacitaire > 95%",
            is_active=True
        ),
        AlertRule(
            alert_type=AlertType.SOUS_UTILISATION,
            threshold_value=50.0,
            severity=AlertSeverity.LOW,
            eg_id=eg_id,
            description="Sous-utilisation < 50%",
            is_active=True
        ),
    ]
    
    for rule in default_rules:
        session.add(rule)
    
    session.commit()
    
    return {"message": f"{len(default_rules)} règles par défaut créées"}


# ========== UI Routes ==========

@ui_router.get("", response_class=HTMLResponse)
async def alert_config_page(request: Request):
    """Page de configuration des seuils d'alertes"""
    return templates.TemplateResponse(
        "alert_config.html",
        {"request": request}
    )
