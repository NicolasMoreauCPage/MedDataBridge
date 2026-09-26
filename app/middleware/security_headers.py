"""En-têtes HTTP de défense applicables à toutes les réponses."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Ajoute des protections navigateur sans imposer de CSP applicative.

    Une CSP exige d'abord l'inventaire des scripts et styles inline existants ;
    les protections ci-dessous sont compatibles avec les pages actuelles.
    """

    def __init__(self, app, *, security_enabled: bool) -> None:
        super().__init__(app)
        self.security_enabled = security_enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.security_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
