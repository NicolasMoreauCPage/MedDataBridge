"""
Middleware pour la gestion des erreurs et le logging des requêtes.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import logging
import time
import traceback

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware qui log toutes les requêtes HTTP."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log de la requête entrante
        logger.info(f"{request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Log du temps de réponse
        duration = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
        
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
            
            # Retourner une réponse d'erreur propre
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Une erreur interne s'est produite",
                    "error_type": type(exc).__name__
                }
            )
