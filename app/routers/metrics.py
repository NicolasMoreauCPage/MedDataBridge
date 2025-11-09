"""API pour les métriques et le monitoring."""
from fastapi import APIRouter
from typing import Optional
from app.utils.structured_logging import metrics


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