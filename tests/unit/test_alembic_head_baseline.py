"""Contrat minimal de la baseline Alembic figée à la tête courante."""

import sys
from pathlib import Path


BASELINE_DIR = Path(__file__).resolve().parents[2] / "alembic/baselines"
sys.path.insert(0, str(BASELINE_DIR))
from head_schema import POSTGRESQL_DDL, SQLITE_DDL  # noqa: E402


def test_versioned_head_baseline_contains_the_complete_application_schema():
    assert len(SQLITE_DDL) == 264
    assert len(POSTGRESQL_DDL) == 276
    postgres_enum_types = {statement.split()[2] for statement in POSTGRESQL_DDL if statement.startswith("CREATE TYPE ")}
    assert postgres_enum_types == {
        "actiontype",
        "dossiertype",
        "entitytype",
        "executionstatus",
        "identifiertype",
        "locationmode",
        "locationphysicaltype",
        "locationstatus",
        "scenariotype",
        "structuretemplatetype",
        "vocabularysystemtype",
    }
    assert any("CREATE TABLE patient" in statement for statement in SQLITE_DDL)
    assert any("CREATE TABLE interopscenario" in statement for statement in SQLITE_DDL)
    assert any("CREATE TABLE outboundmessage" in statement for statement in SQLITE_DDL)
    assert any("ALTER TABLE outboundmessage ADD FOREIGN KEY" in statement for statement in POSTGRESQL_DDL)
