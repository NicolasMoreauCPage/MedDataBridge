"""Typed application configuration loaded from environment variables.

The configuration module is deliberately independent of FastAPI and database
initialisation: importing it must only validate settings, never start a worker
or create a schema. ``load_dotenv`` lives here (rather than in ``app.app``) so
every entry point has the same behaviour.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Mapping

from dotenv import load_dotenv


# Do not override variables explicitly supplied by a service manager, CI, or
# Docker. A local ``.env`` is only a development default.
load_dotenv(override=False)


class ConfigurationError(ValueError):
    """Raised once with a precise, user-actionable configuration diagnostic."""


def _value(environ: Mapping[str, str], name: str, default: str) -> str:
    value = environ.get(name, default)
    return str(value).strip()


def _bool(environ: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = _value(environ, name, "true" if default else "false").lower()
    # Keep compatibility with the historical local files where DEBUG was set
    # to an environment name (for example ``release``) instead of a boolean.
    if raw in {"1", "true", "yes", "on", "dev", "development", "debug"}:
        return True
    if raw in {"0", "false", "no", "off", "release", "prod", "production"}:
        return False
    raise ConfigurationError(
        f"Configuration invalide : {name}={raw!r}. Valeurs attendues : "
        "true/false, 1/0, yes/no ou on/off."
    )


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = _value(environ, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"Configuration invalide : {name}={raw!r}. Un entier strictement positif est attendu."
        ) from exc
    if value <= 0:
        raise ConfigurationError(
            f"Configuration invalide : {name}={raw!r}. Un entier strictement positif est attendu."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings used by application entry points."""

    app_name: str = "IntegraSanté by CPage"
    app_version: str = "1.1.0"
    debug: bool = False
    testing: bool = False
    database_url: str = "sqlite:///./data/medbridge.db"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    secret_key: str = "dev-secret-key-change-in-production"
    file_poll_interval: int = 60
    max_upload_size_mb: int = 20
    max_concurrent_tasks: int = 3
    task_timeout: int = 3600
    task_worker_count: int = 3

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Create settings from an injectable environment, useful for tests."""
        env = os.environ if environ is None else environ
        database_url = _value(env, "DATABASE_URL", cls.database_url)
        if not database_url:
            raise ConfigurationError("Configuration invalide : DATABASE_URL ne peut pas être vide.")
        return cls(
            debug=_bool(env, "DEBUG"),
            testing=_bool(env, "TESTING"),
            database_url=database_url,
            db_echo=_bool(env, "DB_ECHO"),
            db_pool_size=_positive_int(env, "DB_POOL_SIZE", cls.db_pool_size),
            db_max_overflow=_positive_int(env, "DB_MAX_OVERFLOW", cls.db_max_overflow),
            db_pool_timeout=_positive_int(env, "DB_POOL_TIMEOUT", cls.db_pool_timeout),
            secret_key=_value(env, "SECRET_KEY", cls.secret_key),
            file_poll_interval=_positive_int(env, "FILE_POLL_INTERVAL", cls.file_poll_interval),
            max_upload_size_mb=_positive_int(env, "MAX_UPLOAD_SIZE_MB", cls.max_upload_size_mb),
            max_concurrent_tasks=_positive_int(env, "MAX_CONCURRENT_TASKS", cls.max_concurrent_tasks),
            task_timeout=_positive_int(env, "TASK_TIMEOUT", cls.task_timeout),
            task_worker_count=_positive_int(env, "TASK_WORKER_COUNT", cls.task_worker_count),
        )

    def validate_config(self) -> list[str]:
        """Return non-blocking diagnostics after mandatory values were parsed."""
        warnings: list[str] = []
        if self.debug and not self.testing:
            warnings.append("DEBUG est activé hors mode test.")
        if self.database_url.startswith("sqlite:///") and not self.testing:
            warnings.append("La base SQLite est adaptée au développement, pas à une charge multi-processus.")
        return warnings

    def to_dict(self, *, mask_secrets: bool = True) -> dict[str, object]:
        """Expose settings for diagnostics without revealing the session key."""
        values = asdict(self)
        if mask_secrets:
            values["secret_key"] = "***" if self.secret_key else ""
        return values


# Single immutable instance for runtime consumers. Tests which need another
# configuration call ``Settings.from_environment`` instead of mutating globals.
settings = Settings.from_environment()
