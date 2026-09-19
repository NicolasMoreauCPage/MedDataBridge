"""Tests for deterministic, side-effect-free configuration parsing."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.settings import ConfigurationError, Settings


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
