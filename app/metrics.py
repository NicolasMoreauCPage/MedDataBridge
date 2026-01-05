"""
Middleware pour collecter des métriques sur les requêtes HTTP.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware qui collecte des métriques sur les requêtes."""
    
    def __init__(self, app):
        super().__init__(app)
        self.request_count = 0
        self.total_duration = 0.0
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        self.request_count += 1
        self.total_duration += duration
        
        # Ajouter les métriques dans les headers
        response.headers["X-Request-Count"] = str(self.request_count)
        response.headers["X-Avg-Duration"] = f"{self.total_duration / self.request_count:.3f}"
        
        return response
