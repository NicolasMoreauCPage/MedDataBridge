"""Frontière d'authentification globale activée uniquement hors mode LAN."""

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


PUBLIC_PATHS = {"/auth/login", "/auth/login/json", "/auth/refresh", "/health", "/ready", "/api/docs", "/api/redoc", "/api/openapi.json"}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        settings = request.app.state.settings
        if not settings.security_enabled or request.url.path in PUBLIC_PATHS or request.url.path.startswith("/static"):
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentification requise"}, headers={"WWW-Authenticate": "Bearer"})
        try:
            from app.auth import decode_token
            request.state.user = decode_token(authorization.split(None, 1)[1])
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Token invalide"}, headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)
