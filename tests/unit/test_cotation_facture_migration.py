"""Régression de migration pour les anciens statuts de facturation textuels."""

import importlib.util
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text


_MIGRATION_PATH = Path(__file__).parents[2] / "alembic/versions/c7e1f2a4b603_store_cotation_facture_as_boolean.py"
_SPEC = importlib.util.spec_from_file_location("cotation_facture_migration", _MIGRATION_PATH)
assert _SPEC and _SPEC.loader
migration = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migration)
ACT_TABLES = ("ccamact", "ngapact", "ucdact", "lppact")


def test_upgrade_converts_legacy_yes_no_values_to_booleans() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ACT_TABLES:
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, facture VARCHAR NOT NULL)"))
            connection.execute(text(f"INSERT INTO {table} (id, facture) VALUES (1, 'oui'), (2, 'non'), (3, 'trd')"))

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        for table in ACT_TABLES:
            values = connection.execute(text(f"SELECT facture FROM {table} ORDER BY id")).scalars().all()
            assert values == [1, 0, 0]
