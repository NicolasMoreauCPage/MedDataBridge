"""
API endpoints pour la surveillance de la santé du système
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from app.db import get_session
from app.models_endpoints import SystemEndpoint
from app.models_shared import MessageLog
from app.runners import registry
from app.cache import get_redis_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system-health"])


@router.get("/endpoints")
async def get_endpoints_status(session: Session = Depends(get_session)) -> list[Dict[str, Any]]:
    """
    Retourne la liste de tous les endpoints avec leur statut
    """
    try:
        stmt = select(SystemEndpoint)
        endpoints = session.exec(stmt).all()
        running_ids = set(registry.running_ids())
        
        result = []
        for ep in endpoints:
            result.append({
                "id": ep.id,
                "name": ep.name,
                "endpoint_type": ep.endpoint_type,
                "is_active": ep.is_active,
                "status": "RUNNING" if ep.id in running_ids else "STOPPED",
                "host": ep.host,
                "port": ep.port
            })
        
        return result
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des endpoints: {e}")
        return []


@router.get("/messages")
async def get_messages_summary(
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Retourne un résumé des messages selon les filtres
    
    Args:
        status: Filtrer par statut (error, success, etc.)
        date_from: Date de début (YYYY-MM-DD)
        date_to: Date de fin (YYYY-MM-DD)
    """
    try:
        stmt = select(func.count(MessageLog.id))
        
        # Appliquer les filtres
        if status:
            # MessageLog a un champ "status" ou "level"
            stmt = stmt.where(MessageLog.level == status.upper())
        
        if date_from:
            date_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            stmt = stmt.where(MessageLog.created_at >= date_from_dt)
        
        if date_to:
            date_to_dt = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            stmt = stmt.where(MessageLog.created_at < date_to_dt)
        
        total = session.exec(stmt).one()
        
        return {
            "total": total,
            "status": status,
            "date_from": date_from,
            "date_to": date_to
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des messages: {e}")
        return {"total": 0, "error": str(e)}


@router.get("/cache/stats")
async def get_cache_stats_api() -> Dict[str, Any]:
    """
    Retourne les statistiques du cache Redis
    """
    try:
        stats = get_redis_stats()
        return {
            "connected": stats.get("connected", False),
            "hit_rate": stats.get("hit_rate", 0.0),
            "total_keys": stats.get("total_keys", 0),
            "memory_used": stats.get("memory_used_human", "0B"),
            "uptime_seconds": stats.get("uptime_seconds", 0)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats cache: {e}")
        return {
            "connected": False,
            "hit_rate": 0.0,
            "total_keys": 0,
            "memory_used": "0B",
            "uptime_seconds": 0,
            "error": str(e)
        }
