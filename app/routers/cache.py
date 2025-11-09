"""
API de gestion du cache Redis.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from app.services.cache_service import get_cache_service, invalidate_cache

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques du cache Redis.
    
    Returns:
        Statistiques détaillées (mémoire, hits, misses, hit rate)
    """
    cache = get_cache_service()
    stats = cache.get_stats()
    
    if not stats.get("enabled"):
        raise HTTPException(
            status_code=503,
            detail="Cache Redis non disponible"
        )
    
    return stats


@router.post("/invalidate")
async def invalidate_cache_pattern(pattern: str = "*") -> Dict[str, Any]:
    """
    Invalide les clés de cache correspondant au motif.
    
    Args:
        pattern: Motif de clés (ex: "fhir:export:*")
        
    Returns:
        Nombre de clés supprimées
    """
    cache = get_cache_service()
    
    if not cache.enabled:
        raise HTTPException(
            status_code=503,
            detail="Cache Redis non disponible"
        )
    
    deleted_count = cache.delete_pattern(pattern)
    
    return {
        "pattern": pattern,
        "deleted_count": deleted_count,
        "success": True
    }


@router.post("/flush")
async def flush_cache() -> Dict[str, Any]:
    """
    Vide complètement le cache (⚠️ opération destructive).
    
    Returns:
        Confirmation de l'opération
    """
    cache = get_cache_service()
    
    if not cache.enabled:
        raise HTTPException(
            status_code=503,
            detail="Cache Redis non disponible"
        )
    
    success = cache.flush_all()
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du vidage du cache"
        )
    
    return {
        "success": True,
        "message": "Cache vidé complètement"
    }


@router.get("/health")
async def cache_health() -> Dict[str, Any]:
    """
    Vérifie la santé du cache Redis.
    
    Returns:
        Statut de connexion et disponibilité
    """
    cache = get_cache_service()
    
    return {
        "enabled": cache.enabled,
        "connected": cache.enabled and cache.client is not None,
        "status": "healthy" if cache.enabled else "disabled"
    }
