"""
API de gestion du cache Redis.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any
from app.auth import require_role

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats(request: Request) -> Dict[str, Any]:
    """
    Récupère les statistiques du cache Redis.
    
    Returns:
        Statistiques détaillées (mémoire, hits, misses, hit rate)
    """
    cache = request.app.state.cache
    stats = cache.get_stats()
    
    # Retourner les statistiques même si Redis n'est pas activé
    return stats


@router.post("/invalidate")
async def invalidate_cache_pattern(
    request: Request,
    pattern: str = "*",
    _admin=Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Invalide les clés de cache correspondant au motif.
    
    Args:
        pattern: Motif de clés (ex: "fhir:export:*")
        
    Returns:
        Nombre de clés supprimées
    """
    cache = request.app.state.cache
    
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
async def flush_cache(
    request: Request,
    _admin=Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Vide complètement le cache (⚠️ opération destructive).
    
    Returns:
        Confirmation de l'opération
    """
    cache = request.app.state.cache
    
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
async def cache_health(request: Request) -> Dict[str, Any]:
    """
    Vérifie la santé du cache Redis.
    
    Returns:
        Statut de connexion et disponibilité
    """
    cache = request.app.state.cache
    
    return {
        "enabled": cache.enabled,
        "connected": cache.enabled and cache.client is not None,
        "status": "healthy" if cache.enabled else "disabled"
    }
