"""
Middleware pour ajouter les informations de version dans les headers HTTP.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import os


class VersionMiddleware(BaseHTTPMiddleware):
    """Middleware qui ajoute la version de l'application dans les headers."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Ajouter la version dans les headers
        version = os.getenv("APP_VERSION", "dev")
        response.headers["X-App-Version"] = version
        
        return response
