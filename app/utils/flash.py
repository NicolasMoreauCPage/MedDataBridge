from __future__ import annotations

from collections.abc import MutableMapping
from datetime import datetime, timezone
from typing import Literal, TypedDict
from uuid import uuid4

from fastapi import Request


FlashLevel = Literal["info", "success", "warning", "error"]


class FlashPayload(TypedDict):
    id: str
    level: FlashLevel
    message: str
    timestamp: str


def flash(request: Request, message: str, level: FlashLevel = "info") -> None:
    """Store a one-shot notification in the client session.

    Messages are popped by the FlashMessageMiddleware and exposed on
    ``request.state.flash_messages`` for template rendering.
    """
    session = getattr(request, "session", None)
    if not isinstance(session, MutableMapping):
        return

    payload: FlashPayload = {
        "id": uuid4().hex,
        "level": level,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    messages = session.get("_messages")
    if not isinstance(messages, list):
        messages = []
    messages.append(payload)
    session["_messages"] = messages
