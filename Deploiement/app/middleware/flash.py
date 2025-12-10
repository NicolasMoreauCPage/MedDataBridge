def flash(request, message, category="info"):
    """Ajoute un message flash à la session utilisateur."""
    session = getattr(request, "session", None)
    if session is not None:
        messages = session.get("_messages", [])
        messages.append({"message": message, "category": category})
        session["_messages"] = messages
from collections.abc import MutableMapping
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class FlashMessageMiddleware(BaseHTTPMiddleware):
    """Expose flash messages stored in the session on the request state.

    Messages are popped to ensure they are only displayed once.
    """

    async def dispatch(self, request: Request, call_next: Any):
        flash_messages = []
        session = getattr(request, "session", None)
        if isinstance(session, MutableMapping):
            flash_messages = session.pop("_messages", [])
        request.state.flash_messages = flash_messages
        response = await call_next(request)
        return response
