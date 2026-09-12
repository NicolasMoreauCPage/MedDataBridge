"""Contrat de déploiement : une base vide doit pouvoir atteindre ``head``."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def _alembic_config(repository_root: Path, database_path: Path) -> Config:
    config = Config(str(repository_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    return config


def test_alembic_upgrade_head_bootstraps_a_fresh_database(tmp_path: Path):
    database_path = tmp_path / "fresh-medbridge.db"
    repository_root = Path(__file__).resolve().parents[2]
    config = _alembic_config(repository_root, database_path)

    command.upgrade(config, "head")
    command.upgrade(config, "head")  # Une seconde exécution est idempotente.

    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        run_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(scenarioexecutionrun)")
        }
    finally:
        connection.close()

    assert {"patient", "interopscenario", "qualificationcampaign", "outboundmessage", "alembic_version"} <= tables
    assert {"qualification_verdict", "assertion_total", "evidence_json"} <= run_columns
    assert version == "e4b7f0c2d991"


def test_alembic_keeps_incremental_upgrade_for_an_existing_database(tmp_path: Path):
    database_path = tmp_path / "legacy-medbridge.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE interopscenario (id INTEGER PRIMARY KEY);
            CREATE TABLE interopscenariostep (id INTEGER PRIMARY KEY);
            CREATE TABLE scenarioexecutionrun (id INTEGER PRIMARY KEY);
            CREATE TABLE scenarioexecutionsteplog (id INTEGER PRIMARY KEY);
            CREATE TABLE systemendpoint (id INTEGER PRIMARY KEY);
            """
        )
        connection.commit()
    finally:
        connection.close()

    config = _alembic_config(Path(__file__).resolve().parents[2], database_path)
    command.stamp(config, "b2e4f0a13c9e")
    command.upgrade(config, "head")

    connection = sqlite3.connect(database_path)
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(scenarioexecutionrun)")
        }
    finally:
        connection.close()
    assert {"qualification_verdict", "assertion_total", "evidence_json"} <= columns
