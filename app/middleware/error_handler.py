"""
Middleware pour la gestion des erreurs et le logging des requêtes.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import logging
import time
import traceback
from uuid import uuid4

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware qui log toutes les requêtes HTTP."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        correlation_id = request.headers.get("X-Correlation-ID") or uuid4().hex
        request.state.correlation_id = correlation_id
        
        # Log de la requête entrante
        logger.info(f"{request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Log du temps de réponse
        duration = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
        
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware qui capture et gère les erreurs non gérées."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Erreur non gérée: {exc}")
            logger.error(traceback.format_exc())
            
            correlation_id = getattr(request.state, "correlation_id", None)
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Une erreur interne s'est produite",
                        "details": {},
                        "correlation_id": correlation_id,
                        "type": type(exc).__name__,
                    },
                    "detail": "Une erreur interne s'est produite",
                }
            )
            if correlation_id:
                response.headers["X-Correlation-ID"] = correlation_id
            return response
