"""Limitation locale des échecs de connexion.

Cette protection est attachée à chaque instance FastAPI : elle empêche les
rafales sur un processus et ne fait confiance à aucun en-tête de proxy. Une
protection distribuée complémentaire reste nécessaire lorsque l'application
est déployée sur plusieurs processus.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic

from fastapi import Request


class LoginRateLimiter:
    """Bloque temporairement une paire adresse IP / nom d'utilisateur."""

    def __init__(self, *, max_failures: int = 5, window_seconds: int = 900) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    @staticmethod
    def key_for(request: Request, username: str) -> tuple[str, str]:
        client_ip = request.client.host if request.client else "unknown"
        return client_ip, username.strip().casefold()

    def _trim(self, key: tuple[str, str], now: float) -> deque[float]:
        failures = self._failures.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
        return failures

    def retry_after(self, key: tuple[str, str]) -> int | None:
        now = monotonic()
        with self._lock:
            failures = self._trim(key, now)
            if len(failures) < self.max_failures:
                return None
            return max(1, int(self.window_seconds - (now - failures[0])))

    def record_failure(self, key: tuple[str, str]) -> None:
        with self._lock:
            failures = self._trim(key, monotonic())
            self._failures[key] = failures
            failures.append(monotonic())

    def clear(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._failures.pop(key, None)
