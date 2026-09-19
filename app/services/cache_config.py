"""Résolution pure de la configuration Redis."""

import os
from urllib.parse import unquote, urlparse


def redis_settings_from_environment() -> dict[str, object]:
    """Résout REDIS_URL avant les variables historiques hôte/port."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        parsed = urlparse(redis_url)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("REDIS_URL doit être une URL redis:// ou rediss:// valide")
        database = parsed.path.strip("/")
        return {
            "host": parsed.hostname,
            "port": parsed.port or 6379,
            "db": int(database) if database else 0,
            "password": unquote(parsed.password) if parsed.password else None,
        }
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": int(os.getenv("REDIS_DB", "0")),
        "password": os.getenv("REDIS_PASSWORD"),
    }
