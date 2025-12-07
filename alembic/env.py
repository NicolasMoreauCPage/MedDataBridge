from __future__ import annotations
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from sqlmodel import SQLModel

# Import models to register tables
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.models import Patient, Dossier, Venue, Mouvement, Sequence
from app.models_contacts import PatientContact, VenueContact
from app.models_endpoints import SystemEndpoint, MessageLog
from app.models_vocabulary import VocabularySystem, VocabularyValue, VocabularyMapping
from app.models_structure import GHTContext, IdentifierNamespace
from app.models_structure import EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.models_identifiers import Identifier
from app.models_practitioners import MedecinResponsable  # Médecins responsables
from app import models_scenarios  # ensure scenario models are registered
from app import models_workflows  # ensure workflow models are registered
from app.db import get_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# Get database URL from environment or config
database_url = os.getenv("SQLALCHEMY_DATABASE_URL") or get_database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed)."""
    url = database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a real database connection."""
    configuration = config.get_section(config.config_ini_section)
    # Override sqlalchemy.url with the dynamic database URL
    configuration["sqlalchemy.url"] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
