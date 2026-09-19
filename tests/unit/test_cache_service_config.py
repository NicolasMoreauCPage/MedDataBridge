"""Configuration Redis indépendante du réseau pour les workers et Compose."""

import pytest

from app.services.cache_config import redis_settings_from_environment


def test_redis_url_takes_precedence_for_container_dns(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://:secret@redis:6380/3")
    monkeypatch.setenv("REDIS_HOST", "localhost")

    assert redis_settings_from_environment() == {
        "host": "redis",
        "port": 6380,
        "db": 3,
        "password": "secret",
    }


def test_invalid_redis_url_has_a_clear_diagnostic(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "http://not-redis")

    with pytest.raises(ValueError, match="REDIS_URL"):
        redis_settings_from_environment()
