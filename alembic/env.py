from __future__ import annotations
from logging.config import fileConfig
from sqlalchemy import engine_from_config, inspect, pool, text
from alembic import context
from alembic.script import ScriptDirectory
from sqlmodel import SQLModel

# Import models to register tables
import sys
import os
from pathlib import Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, str(Path(__file__).resolve().parent / "baselines"))
from head_schema import create_head_schema  # noqa: E402
# ``app.db`` est le registre exhaustif réellement utilisé par l'application
# (modèles HPRIM, contacts, cotations, campagnes, etc.). L'importer ici évite
# qu'une installation neuve Alembic crée un sous-ensemble de tables.
from app import db as _application_model_registry  # noqa: F401

config = context.config
# Production and Docker provide DATABASE_URL at runtime. Retain the value from
# alembic.ini for local SQLite development and tests that explicitly override
# the Alembic configuration.
configured_url = config.get_main_option("sqlalchemy.url")
ini_url = config.file_config.get(config.config_ini_section, "sqlalchemy.url")
if os.getenv("DATABASE_URL") and configured_url == ini_url:
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
if (
    config.config_file_name is not None
    and config.attributes.get("configure_logger", True)
    and "PYTEST_CURRENT_TEST" not in os.environ
):
    # ``fileConfig`` remplace les handlers du logger racine. Lorsqu'Alembic est
    # invoqué comme une bibliothèque (notamment par pytest), ce comportement
    # ferait disparaître les handlers de l'hôte pour tout le reste du processus.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def _bootstrap_empty_database(connection) -> bool:
    """Installe une baseline fiable lorsque la base est entièrement vide.

    L'historique Alembic antérieur au projet ne contient pas le DDL initial :
    plusieurs révisions supposent que les tables applicatives existent déjà.
    Une nouvelle installation ne peut donc pas rejouer cette histoire sans
    erreur. Pour une cible ``head`` vide, on crée le schéma courant (comme
    l'initialisation applicative) puis on le marque à la révision tête.

    Ce chemin ne concerne *que* les bases sans aucune table. Une base existante
    conserve le comportement Alembic normal et reçoit les migrations restantes.
    """
    if inspect(connection).get_table_names():
        return False

    requested_revision = context.get_revision_argument()
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError("La baseline exige une unique révision Alembic tête")
    head = heads[0]
    if requested_revision not in {"head", head}:
        return False

    create_head_schema(connection)
    # Le bootstrap installe exclusivement le schéma DDL versionné. Les jeux de
    # données de référence sont lancés séparément, après ``alembic upgrade
    # head``, afin qu'une migration ne crée jamais de données métier implicites.
    connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    connection.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
        {"revision": head},
    )
    # SQLite auto-valide le DDL, mais pas nécessairement l'INSERT de version
    # lorsque la connexion est fermée après cette transaction Alembic. Les
    # autres SGBD restent gérés par ``context.begin_transaction``.
    if connection.dialect.name == "sqlite":
        connection.commit()
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            if not _bootstrap_empty_database(connection):
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
