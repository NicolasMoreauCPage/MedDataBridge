"""API pour les métriques et le monitoring."""
from fastapi import APIRouter, Depends
from typing import Optional, Dict, Any
from app.utils.structured_logging import metrics
from app.auth import require_role
from app.services.cache_service import get_cache_service


router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@router.get("/operations", response_model=dict)
async def get_operation_metrics(operation: Optional[str] = None):
    """
    Récupère les métriques d'opérations.
    
    Args:
        operation: Nom de l'opération (optionnel). Si non fourni, retourne toutes les métriques.
        
    Returns:
        Dictionnaire avec les métriques:
        - count: Nombre total d'exécutions
        - success_count: Nombre de succès
        - error_count: Nombre d'erreurs
        - total_duration: Durée totale (secondes)
        - avg_duration: Durée moyenne (secondes)
        - min_duration: Durée minimale (secondes)
        - max_duration: Durée maximale (secondes)
        - success_rate: Taux de succès (0-1)
    """
    return metrics.get_metrics(operation)


@router.delete("/operations", response_model=dict)
async def reset_metrics():
    """
    Réinitialise toutes les métriques.
    
    Returns:
        Message de confirmation
    """
    metrics.reset()
    return {
        "status": "success",
        "message": "Métriques réinitialisées"
    }


@router.get("/dashboard", response_model=dict)
async def get_metrics_dashboard():
    """
    Récupère un tableau de bord complet des métriques de l'application.
    
    Returns:
        Dictionnaire avec:
        - operations: Métriques détaillées par opération
        - summary: Statistiques globales
        - health: Statut de santé
    """
    operation_metrics = metrics.get_metrics()
    
    # Calculer des statistiques globales
    total_operations = sum(m.get("count", 0) for m in operation_metrics.values())
    total_errors = sum(m.get("error_count", 0) for m in operation_metrics.values())
    total_success = sum(m.get("success_count", 0) for m in operation_metrics.values())
    
    health_status = "healthy"
    error_rate = 0
    if total_operations > 0:
        error_rate = total_errors / total_operations
        if error_rate > 0.1:  # Plus de 10% d'erreurs
            health_status = "degraded"
        if error_rate > 0.5:  # Plus de 50% d'erreurs
            health_status = "unhealthy"
    
    return {
        "summary": {
            "total_operations": total_operations,
            "total_success": total_success,
            "total_errors": total_errors,
            "error_rate": round(error_rate * 100, 2),
            "success_rate": round((total_success / total_operations * 100) if total_operations > 0 else 0, 2),
            "operations_tracked": len(operation_metrics)
        },
        "health": {
            "status": health_status,
            "message": "All systems operational" if health_status == "healthy" else f"Error rate: {round(error_rate * 100, 2)}%"
        },
        "operations": operation_metrics
    }


@router.get("/health", response_model=dict)
async def health_check():
    """
    Endpoint de health check.
    
    Returns:
        Statut de santé de l'application
    """
    operation_metrics = metrics.get_metrics()
    
    # Calculer des statistiques globales
    total_operations = sum(m.get("count", 0) for m in operation_metrics.values())
    total_errors = sum(m.get("error_count", 0) for m in operation_metrics.values())
    
    health_status = "healthy"
    if total_operations > 0:
        error_rate = total_errors / total_operations
        if error_rate > 0.1:  # Plus de 10% d'erreurs
            health_status = "degraded"
        if error_rate > 0.5:  # Plus de 50% d'erreurs
            health_status = "unhealthy"
    
    return {
        "status": health_status,
        "total_operations": total_operations,
        "total_errors": total_errors,
        "operations_tracked": len(operation_metrics)
    }


@router.get("/cache", response_model=dict)
async def get_cache_metrics(
    _: None = Depends(require_role(["admin", "moderator"]))
) -> Dict[str, Any]:
    """
    Récupère les métriques de cache Redis.
    
    Accessible uniquement aux administrateurs et modérateurs.
    
    Returns:
        Dictionnaire contenant:
        - enabled: Cache activé ou non
        - used_memory: Mémoire utilisée
        - total_connections: Nombre de connexions
        - total_commands: Nombre de commandes exécutées
        - keyspace_hits: Nombre de hits
        - keyspace_misses: Nombre de miss
        - hit_rate: Taux de succès en %
    """
    cache = get_cache_service()
    stats = cache.get_stats()
    
    # Ajouter des métriques calculées
    if stats.get("enabled"):
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total_ops = hits + misses
        
        stats["total_operations"] = total_ops
        stats["hits_percentage"] = stats.get("hit_rate", 0)
        stats["misses_percentage"] = round(100 - stats.get("hit_rate", 0), 2) if total_ops > 0 else 0
    
    return stats


@router.get("/cache/health", response_model=dict)
async def cache_health_check() -> Dict[str, Any]:
    """
    Vérifie la santé du service de cache.
    
    Endpoint public pour les health checks.
    
    Returns:
        Statut du cache (healthy/unhealthy)
    """
    cache = get_cache_service()
    
    if not cache.enabled:
        return {
            "status": "unhealthy",
            "message": "Cache service not available",
            "enabled": False
        }
    
    # Test simple de connectivité
    try:
        test_key = "health:check"
        cache.set(test_key, "ok", ttl=5)
        value = cache.get(test_key)
        cache.delete(test_key)
        
        if value == "ok":
            return {
                "status": "healthy",
                "message": "Cache service operational",
                "enabled": True
            }
        else:
            return {
                "status": "degraded",
                "message": "Cache reads not working correctly",
                "enabled": True
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Cache error: {str(e)}",
            "enabled": False
        }