"""
Middleware pour la gestion des erreurs et le logging des requêtes.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import logging
import time
from uuid import uuid4

from app.utils.error_handling import generic_exception_handler

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware qui log toutes les requêtes HTTP."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        correlation_id = request.headers.get("X-Correlation-ID") or uuid4().hex
        request.state.correlation_id = correlation_id
        
        # Le même identifiant relie le log de requête, l'enveloppe d'erreur et
        # les journaux de livraison créés par les routes appelées.
        logger.info(
            "HTTP request received",
            extra={
                "correlation_id": correlation_id,
                "http_method": request.method,
                "http_path": request.url.path,
            },
        )
        
        response = await call_next(request)
        
        # Log du temps de réponse, y compris lorsqu'un gestionnaire d'exception
        # FastAPI a produit une réponse 4xx/5xx.
        duration = time.time() - start_time
        logger.info(
            "HTTP request completed",
            extra={
                "correlation_id": correlation_id,
                "http_method": request.method,
                "http_path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": duration,
            },
        )
        
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware qui capture et gère les erreurs non gérées."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Frontière technique volontaire : les erreurs imprévues passent
            # par le même contrat public et le même log structuré que les
            # gestionnaires FastAPI.
            return await generic_exception_handler(request, exc)
