"""Service de calcul de métriques de conformité par EJ.

Ce module fournit des fonctions pour calculer:
- Taux de conformité des messages reçus/émis
- Issues récurrentes par type
- Évolution temporelle des métriques
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sqlmodel import Session, select, func, and_
from collections import Counter

from app.models_endpoints import MessageLog
from app.models_structure_fhir import EntiteJuridique


def compute_conformity_rate(
    session: Session,
    ej_id: int,
    days: int = 7,
    direction: Optional[str] = None
) -> Dict[str, any]:
    """Calcule le taux de conformité des messages pour une EJ sur une période.
    
    Args:
        session: Session SQLModel
        ej_id: ID de l'entité juridique
        days: Nombre de jours à analyser (défaut: 7)
        direction: 'inbound', 'outbound' ou None pour les deux
        
    Returns:
        Dict avec total, valides, taux, période
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Requête de base
    stmt = select(MessageLog).where(
        and_(
            MessageLog.ej_id == ej_id,
            MessageLog.created_at >= cutoff
        )
    )
    
    if direction:
        stmt = stmt.where(MessageLog.direction == direction)
    
    messages = session.exec(stmt).all()
    
    total = len(messages)
    if total == 0:
        return {
            "total": 0,
            "valid": 0,
            "rate": 0.0,
            "period_days": days,
            "direction": direction or "all"
        }
    
    # Compter les messages valides (pas d'issues severity=error)
    valid = 0
    for msg in messages:
        if msg.pam_validation_issues:
            # Parser JSON issues et vérifier severity
            import json
            try:
                issues = json.loads(msg.pam_validation_issues)
                has_error = any(i.get("severity") == "error" for i in issues)
                if not has_error:
                    valid += 1
            except:
                pass
        else:
            valid += 1
    
    return {
        "total": total,
        "valid": valid,
        "rate": round((valid / total) * 100, 1),
        "period_days": days,
        "direction": direction or "all"
    }


def get_recurring_issues(
    session: Session,
    ej_id: int,
    days: int = 7,
    top_n: int = 10
) -> List[Dict[str, any]]:
    """Retourne les issues les plus fréquentes pour une EJ.
    
    Args:
        session: Session SQLModel
        ej_id: ID de l'entité juridique
        days: Nombre de jours à analyser
        top_n: Nombre d'issues à retourner
        
    Returns:
        Liste de dicts {code, message, count, severity}
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    stmt = select(MessageLog).where(
        and_(
            MessageLog.ej_id == ej_id,
            MessageLog.created_at >= cutoff,
            MessageLog.pam_validation_issues.isnot(None)
        )
    )
    
    messages = session.exec(stmt).all()
    
    # Collecter toutes les issues
    issue_counter = Counter()
    issue_details = {}
    
    import json
    for msg in messages:
        if not msg.pam_validation_issues:
            continue
        try:
            issues = json.loads(msg.pam_validation_issues)
            for issue in issues:
                code = issue.get("code", "UNKNOWN")
                issue_counter[code] += 1
                if code not in issue_details:
                    issue_details[code] = {
                        "message": issue.get("message", ""),
                        "severity": issue.get("severity", "info")
                    }
        except:
            pass
    
    # Top N
    top_issues = []
    for code, count in issue_counter.most_common(top_n):
        details = issue_details.get(code, {})
        top_issues.append({
            "code": code,
            "message": details.get("message", ""),
            "count": count,
            "severity": details.get("severity", "info")
        })
    
    return top_issues


def get_timeline_metrics(
    session: Session,
    ej_id: int,
    days: int = 30
) -> List[Dict[str, any]]:
    """Retourne l'évolution jour par jour des métriques de conformité.
    
    Args:
        session: Session SQLModel
        ej_id: ID de l'entité juridique
        days: Nombre de jours à analyser
        
    Returns:
        Liste de dicts {date, total, valid, rate} par jour
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    stmt = select(MessageLog).where(
        and_(
            MessageLog.ej_id == ej_id,
            MessageLog.created_at >= cutoff
        )
    )
    
    messages = session.exec(stmt).all()
    
    # Grouper par jour
    daily_stats = {}
    import json
    
    for msg in messages:
        day = msg.created_at.date()
        if day not in daily_stats:
            daily_stats[day] = {"total": 0, "valid": 0}
        
        daily_stats[day]["total"] += 1
        
        # Vérifier validité
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
            daily_stats[day]["valid"] += 1
    
    # Convertir en liste triée
    timeline = []
    for day in sorted(daily_stats.keys()):
        stats = daily_stats[day]
        rate = round((stats["valid"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0
        timeline.append({
            "date": day.isoformat(),
            "total": stats["total"],
            "valid": stats["valid"],
            "rate": rate
        })
    
    return timeline


def get_ej_summary(session: Session, ej_id: int) -> Dict[str, any]:
    """Retourne un résumé complet de conformité pour une EJ.
    
    Combine les métriques principales en un seul appel.
    """
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        return None
    
    # Métriques période courte (7 jours)
    conformity_7d = compute_conformity_rate(session, ej_id, days=7)
    conformity_in_7d = compute_conformity_rate(session, ej_id, days=7, direction="inbound")
    conformity_out_7d = compute_conformity_rate(session, ej_id, days=7, direction="outbound")
    
    # Issues récurrentes
    recurring = get_recurring_issues(session, ej_id, days=7, top_n=5)
    
    # Timeline 30 jours
    timeline = get_timeline_metrics(session, ej_id, days=30)
    
    return {
        "ej": {
            "id": ej.id,
            "name": ej.name,
            "finess_ej": ej.finess_ej,
            "strict_pam_fr": ej.strict_pam_fr
        },
        "conformity_7d": conformity_7d,
        "conformity_inbound_7d": conformity_in_7d,
        "conformity_outbound_7d": conformity_out_7d,
        "recurring_issues": recurring,
        "timeline_30d": timeline
    }
