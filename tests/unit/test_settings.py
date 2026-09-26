"""Tests for deterministic, side-effect-free configuration parsing."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.settings import ConfigurationError, Settings


def _session_middleware_options(application):
    return next(
        middleware.kwargs
        for middleware in application.user_middleware
        if middleware.cls.__name__ == "SessionMiddleware"
    )


def test_settings_parse_typed_environment_values():
    settings = Settings.from_environment(
        {
            "DEBUG": "yes",
            "TESTING": "0",
            "DATABASE_URL": "sqlite:///./tmp/test.db",
            "DB_POOL_SIZE": "7",
            "FILE_POLL_INTERVAL": "15",
        }
    )

    assert settings.debug is True
    assert settings.testing is False
    assert settings.db_pool_size == 7
    assert settings.file_poll_interval == 15
    assert settings.database_url.endswith("tmp/test.db")


def test_security_is_disabled_by_default_and_can_be_enabled():
    assert Settings.from_environment({}).security_enabled is False
    assert Settings.from_environment(
        {
            "SECURITY_ENABLED": "true",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "BOOTSTRAP_ADMIN_PASSWORD": "administrateur-test-fort",
        }
    ).security_enabled is True


def test_create_app_only_mounts_login_routes_when_security_is_enabled():
    from app.app import create_app

    local_app = create_app(Settings(testing=True, security_enabled=False))
    secured_app = create_app(Settings(
        testing=True,
        security_enabled=True,
        secret_key="a" * 32,
        jwt_secret_key="b" * 32,
        bootstrap_admin_username="admin",
        bootstrap_admin_password="administrateur-test-fort",
    ))

    local_paths = {route.path for route in local_app.routes}
    secured_paths = {route.path for route in secured_app.routes}

    assert "/auth/login" not in local_paths
    assert "/auth/login" in secured_paths
    assert "/api/admin/users" not in local_paths
    assert "/api/admin/users" in secured_paths

    assert _session_middleware_options(local_app)["https_only"] is False
    assert _session_middleware_options(secured_app)["https_only"] is True


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("DEBUG", "sometimes", "DEBUG='sometimes'"),
        ("DB_POOL_SIZE", "many", "DB_POOL_SIZE='many'"),
        ("FILE_POLL_INTERVAL", "0", "FILE_POLL_INTERVAL='0'"),
    ],
)
def test_settings_report_a_single_readable_invalid_value(name, value, expected):
    with pytest.raises(ConfigurationError, match=expected):
        Settings.from_environment({name: value})


def test_settings_diagnostic_serialisation_masks_the_session_key():
    settings = Settings.from_environment({"SECRET_KEY": "session-key"})

    assert settings.to_dict()["secret_key"] == "***"
    assert settings.to_dict(mask_secrets=False)["secret_key"] == "session-key"


def test_importing_application_in_testing_mode_does_not_create_a_database(tmp_path):
    database_path = tmp_path / "must-not-be-created.db"
    environment = {
        **os.environ,
        "TESTING": "1",
        "DATABASE_URL": f"sqlite:///{database_path}",
    }
    repository_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-c", "import app.app; print('imported')"],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout
    assert not database_path.exists()


def test_importing_application_in_lan_mode_does_not_require_a_jwt_secret(tmp_path):
    """Le mode sans login doit respecter la procédure de démarrage locale."""
    database_path = tmp_path / "lan-mode.db"
    environment = {
        **os.environ,
        "TESTING": "0",
        "DEBUG": "0",
        "SECURITY_ENABLED": "false",
        "SECRET_KEY": "",
        "JWT_SECRET_KEY": "",
        "DATABASE_URL": f"sqlite:///{database_path}",
    }
    repository_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-c", "import app.app; print('lan-imported')"],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "lan-imported" in result.stdout
    assert not database_path.exists()


def test_create_app_uses_injected_validated_settings():
    from app.app import create_app

    injected = Settings(
        app_name="MedBridge test factory",
        app_version="9.9.9",
        debug=True,
        testing=True,
        secret_key="factory-test-key",
    )
    application = create_app(injected)

    assert application.title == "MedBridge test factory"
    assert application.version == "9.9.9"
    assert application.debug is True
    assert application.state.settings is injected
    with TestClient(application) as client:
        response = client.get("/api/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "MedBridge test factory"


def test_create_app_isolates_database_and_background_services(tmp_path):
    from sqlmodel import SQLModel

    from app.app import create_app

    first = create_app(
        Settings(
            testing=True,
            database_url=f"sqlite:///{tmp_path / 'first.db'}",
            secret_key="first-factory-key",
        )
    )
    second = create_app(
        Settings(
            testing=True,
            database_url=f"sqlite:///{tmp_path / 'second.db'}",
            secret_key="second-factory-key",
        )
    )

    assert first.state.engine is not second.state.engine
    assert first.state.session_factory is not second.state.session_factory
    assert first.state.mllp_manager is not second.state.mllp_manager
    assert first.state.scheduler is not second.state.scheduler
    assert first.state.cache is not second.state.cache
    assert first.state.cache.enabled is False
    assert str(first.state.engine.url).endswith("first.db")
    assert str(second.state.engine.url).endswith("second.db")

    SQLModel.metadata.create_all(first.state.engine)
    SQLModel.metadata.create_all(second.state.engine)
    with TestClient(first) as first_client, TestClient(second) as second_client:
        assert first_client.get("/ready").status_code == 200
        assert second_client.get("/ready").status_code == 200


def test_postgresql_engine_uses_a_compatible_pool_configuration():
    repository_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.db import engine; print(type(engine.pool).__name__)",
        ],
        cwd=repository_root,
        env={
            **os.environ,
            "TESTING": "0",
            "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/medbridge",
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "QueuePool" in result.stdout
