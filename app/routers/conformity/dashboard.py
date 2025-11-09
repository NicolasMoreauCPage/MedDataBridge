"""Router conformité: dashboard par EJ et vues messages.

Ce module expose:
- Dashboard par EJ avec métriques de conformité
- Liste des messages par EJ avec détail validation
- Vue de comparaison messages
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, and_
from datetime import datetime, timedelta

from app.db import get_session
from app.models_structure_fhir import EntiteJuridique
from app.models_endpoints import MessageLog
from app.services.conformity.metrics import get_ej_summary
from app.dependencies.ght import require_ght_context


def get_templates(request: Request):
    return request.app.state.templates


router = APIRouter(
    prefix="/conformity",
    tags=["conformity"],
    dependencies=[Depends(require_ght_context)]
)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def conformity_home(request: Request, session: Session = Depends(get_session)):
    """Page d'accueil conformité: liste des EJ avec aperçu métriques."""
    templates = get_templates(request)
    
    # Récupérer toutes les EJ
    ej_list = session.exec(select(EntiteJuridique)).all()
    
    # Calculer métriques rapides pour chaque EJ
    ej_stats = []
    for ej in ej_list:
        # Compter messages 7 derniers jours
        cutoff = datetime.utcnow() - timedelta(days=7)
        count_stmt = select(MessageLog).where(
            and_(
                MessageLog.ej_id == ej.id,
                MessageLog.created_at >= cutoff
            )
        )
        messages = session.exec(count_stmt).all()
        
        total = len(messages)
        if total > 0:
            # Calculer taux de validité rapide
            import json
            valid = 0
            for msg in messages:
                is_valid = True
                if msg.pam_validation_issues:
                    try:
                        issues = json.loads(msg.pam_validation_issues)
                        has_error = any(i.get("severity") == "error" for i in issues)
                        if has_error:
                            is_valid = False
                    except:
                        pass
                if is_valid:
                    valid += 1
            rate = round((valid / total) * 100, 1) if total > 0 else 0
        else:
            valid = 0
            rate = 0
        
        ej_stats.append({
            "ej": ej,
            "total_7d": total,
            "valid_7d": valid,
            "rate_7d": rate
        })
    
    return templates.TemplateResponse(request, "conformity_home.html", {
        "title": "Conformité par Entité Juridique",
        "ej_stats": ej_stats
    })


@router.get("/ej/{ej_id:int}", response_class=HTMLResponse)
def ej_dashboard(ej_id: int, request: Request, session: Session = Depends(get_session)):
    """Dashboard détaillé pour une EJ spécifique."""
    templates = get_templates(request)
    
    # Récupérer le résumé complet
    summary = get_ej_summary(session, ej_id)
    
    if not summary:
        return templates.TemplateResponse(request, "not_found.html", {
            "title": "EJ introuvable"
        }, status_code=404)
    
    return templates.TemplateResponse(request, "conformity_dashboard.html", {
        "title": f"Conformité - {summary['ej']['name']}",
        "summary": summary
    })


@router.get("/ej/{ej_id:int}/messages", response_class=HTMLResponse)
def ej_messages(ej_id: int, request: Request, session: Session = Depends(get_session)):
    """Liste des messages pour une EJ avec détail validation."""
    templates = get_templates(request)
    
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        return templates.TemplateResponse(request, "not_found.html", {
            "title": "EJ introuvable"
        }, status_code=404)
    
    # Récupérer messages des 30 derniers jours
    cutoff = datetime.utcnow() - timedelta(days=30)
    stmt = select(MessageLog).where(
        and_(
            MessageLog.ej_id == ej_id,
            MessageLog.created_at >= cutoff
        )
    ).order_by(MessageLog.created_at.desc())
    
    messages = session.exec(stmt).all()
    
    # Enrichir avec statut validation
    import json
    message_list = []
    for msg in messages:
        is_valid = True
        error_count = 0
        warn_count = 0
        
        if msg.pam_validation_issues:
            try:
                issues = json.loads(msg.pam_validation_issues)
                for issue in issues:
                    severity = issue.get("severity", "info")
                    if severity == "error":
                        error_count += 1
                        is_valid = False
                    elif severity == "warn":
                        warn_count += 1
            except:
                pass
        
        message_list.append({
            "log": msg,
            "is_valid": is_valid,
            "error_count": error_count,
            "warn_count": warn_count
        })
    
    return templates.TemplateResponse(request, "conformity_messages.html", {
        "title": f"Messages - {ej.name}",
        "ej": ej,
        "messages": message_list
    })


@router.get("/ej/{ej_id:int}/messages/{message_id:int}", response_class=HTMLResponse)
def message_detail(ej_id: int, message_id: int, request: Request, session: Session = Depends(get_session)):
    """Détail d'un message avec validation complète et possibilité de rejouer."""
    templates = get_templates(request)
    
    msg = session.get(MessageLog, message_id)
    if not msg or msg.ej_id != ej_id:
        return templates.TemplateResponse(request, "not_found.html", {
            "title": "Message introuvable"
        }, status_code=404)
    
    # Parser issues
    import json
    issues = []
    if msg.pam_validation_issues:
        try:
            issues = json.loads(msg.pam_validation_issues)
        except:
            pass
    
    # Classifier par sévérité
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warn"]
    infos = [i for i in issues if i.get("severity") == "info"]
    
    return templates.TemplateResponse(request, "conformity_message_detail.html", {
        "title": f"Message {msg.id} - Détail validation",
        "message": msg,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "all_issues": issues
    })


@router.post("/ej/{ej_id:int}/messages/{message_id:int}/revalidate")
def revalidate_message(ej_id: int, message_id: int, request: Request, session: Session = Depends(get_session)):
    """Rejoue la validation sur un message existant."""
    msg = session.get(MessageLog, message_id)
    if not msg or msg.ej_id != ej_id:
        return RedirectResponse(url=f"/conformity/ej/{ej_id}/messages", status_code=303)
    
    # Rejouer validation
    from app.services.pam_validation import validate_pam
    result = validate_pam(msg.raw_message, direction=msg.direction or "inbound")
    
    # Mettre à jour issues
    import json
    msg.pam_validation_issues = json.dumps([
        {
            "code": i.code,
            "message": i.message,
            "severity": i.severity
        }
        for i in result.issues
    ])
    session.add(msg)
    session.commit()
    
    return RedirectResponse(url=f"/conformity/ej/{ej_id}/messages/{message_id}", status_code=303)
