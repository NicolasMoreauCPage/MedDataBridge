"""
Accès base de données et aides de séquence

Contenu
- Création du moteur SQLModel/SQLite (fichier local `medbridge.db`).
- Utilitaires de session via dépendance `get_session` (FastAPI Depends).
- Gestion de séquences applicatives simples (table `Sequence`) avec `peek_next_sequence`
    et `get_next_sequence`.
- Hook `before_flush` pour normaliser certains champs date/heure (chaînes → datetime).

Notes
- En contexte transactionnel (session.in_transaction()), on privilégie `flush()`
    pour éviter des commits imbriqués.
"""

from datetime import datetime
import logging

from sqlmodel import SQLModel, create_engine, Session, select, text
from sqlalchemy import event
from pathlib import Path
from typing import Optional

# Import ALL models to ensure tables are registered
from app.models import Sequence, Patient, Dossier, Venue, Mouvement  # noqa: F401 - ORM registry
from app.models.shared import SystemEndpoint, MessageLog  # noqa: F401 - ORM registry
from app.models import endpoints as models_endpoints  # noqa: F401 - ORM registry
from app.models.vocabulary import VocabularyMapping, VocabularySystem, VocabularyValue  # noqa: F401 - ORM registry
from app.models_structure import GHTContext, IdentifierNamespace, EntiteJuridique, EntiteGeographique  # noqa: F401 - ORM registry
from app.models.hprim_models import HprimMessage, HprimCCAMAct, HprimNGAPAct, HprimExchangeAct  # noqa: F401 - ORM registry
from app.models.outbox import OutboundMessage  # noqa: F401 - ORM registry
from app.models.identifiers import Identifier  # noqa: F401 - ORM registry
from app.models.practitioners import MedecinResponsable  # noqa: F401 - ORM registry / FK resolution
from app import models_scenarios  # noqa: F401 - ORM registry
from app.models import scenario_runs as models_scenario_runs  # noqa: F401 - ORM registry
from app.models import scenario_target_profiles as models_scenario_target_profiles  # noqa: F401 - ORM registry
from app.models import qualification as models_qualification  # noqa: F401 - ORM registry
from app.models import scenario_review as models_scenario_review  # noqa: F401 - ORM registry
from app.models import appointments as models_appointments  # noqa: F401 - ORM registry
from app.models import analytics as models_analytics  # noqa: F401 - ORM registry
try:  # Import optionnel de l'init des templates (peut échouer si fichiers absents)
    from app.services.scenario_template_init import init_scenario_templates  # noqa: E402
except Exception:  # pragma: no cover
    init_scenario_templates = None  # type: ignore
from app.models import workflows as models_workflows  # noqa: F401 - ORM registry


# Use in-memory SQLite for tests, file-based otherwise
from sqlalchemy.pool import StaticPool

# Import de la configuration centralisée
from config.settings import settings
import sys

logger = logging.getLogger(__name__)

# Consider we're in testing mode when either the Settings say so or we're
# running under pytest (common for local test runs launched via
# `python -m pytest`). This makes SQLModel.metadata.create_all() run for
# in-memory engines during test collection so fixtures relying on an
# initialized schema don't fail with "no such table".
_running_under_pytest = any("pytest" in arg for arg in sys.argv)
testing_flag = bool(settings.testing or _running_under_pytest)


def create_database_engine(runtime_settings=settings, *, in_memory: bool = False):
    """Construit un moteur isolé sans modifier l'état global du module."""
    from sqlalchemy.pool import QueuePool

    database_url = "sqlite:///:memory:" if in_memory else runtime_settings.database_url
    is_sqlite = database_url.lower().startswith("sqlite")
    engine_kwargs = {
        "echo": runtime_settings.db_echo,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    if is_sqlite:
        engine_kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": 30.0,
        }
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs.update(
            {
                "poolclass": QueuePool,
                "pool_size": runtime_settings.db_pool_size,
                "max_overflow": runtime_settings.db_max_overflow,
                "pool_timeout": runtime_settings.db_pool_timeout,
            }
        )
    return create_engine(database_url, **engine_kwargs)


if testing_flag:
    engine = create_database_engine(settings, in_memory=True)
    # When running tests in-process (TESTING=1) we need the schema
    # created on the in-memory engine so TestClient-based tests can
    # operate without requiring an explicit init_db() call.
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as exc:
        # If schema creation fails for any reason, allow tests to
        # manage their own schema creation as some fixtures do.
        logger.debug("Test schema creation deferred to fixtures", exc_info=exc)
else:
    engine = create_database_engine(settings)


def make_session_dependency(database_engine):
    """Crée une dépendance FastAPI liée à un moteur précis."""
    def _get_runtime_session():
        session = Session(database_engine)
        try:
            yield session
        finally:
            session.close()

    return _get_runtime_session


def make_session_factory(database_engine):
    """Crée une fabrique de sessions courtes liée à un moteur précis."""
    return lambda: Session(database_engine)

def migrate_database(database_url: str | None = None) -> None:
    """Met une base applicative à jour exclusivement via Alembic.

    Cette fonction est destinée au cycle de vie hors tests. Elle utilise l'URL
    effectivement configurée par l'application plutôt que celle codée dans
    ``alembic.ini`` : SQLite local, PostgreSQL Compose et déploiements suivent
    ainsi exactement la même chaîne de migration.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url or str(engine.url))
    command.upgrade(config, "head")


def init_db() -> None:
    """Initialise la base par l'unique chemin de schéma supporté.

    Les tests en mémoire utilisent la metadata pour rester rapides. Tous les
    autres environnements passent obligatoirement par Alembic.
    """
    if testing_flag:
        SQLModel.metadata.create_all(engine)
    else:
        migrate_database(str(engine.url))
    if init_scenario_templates:
        with Session(engine) as _s:
            init_scenario_templates(_s)

def get_session():
    """Dépendance FastAPI: fournit une session courte.

    Use explicit open/close so we can catch DBAPI errors during close
    (some SQLite builds raise on rollback when no transaction is active)
    and avoid the exception bubbling out of the ASGI request finalizer.
    """
    import logging
    logger = logging.getLogger(__name__)
    session = Session(engine)
    try:
        yield session
    finally:
        try:
            session.close()
        except Exception as e:
            logger.warning("Error while closing DB session: %s", e)

def session_factory():
    """Factory explicite pour obtenir une session non gérée (scripts utilitaires)."""
    return Session(engine)

def _get_seq(session: Session, name: str) -> Sequence:
    seq: Optional[Sequence] = session.get(Sequence, name)
    if not seq:
        seq = Sequence(name=name, value=0)
        session.add(seq)
        # If we're already inside a transaction (e.g. session.begin()), don't commit here.
        # Commit only when called from outside a transactional context; otherwise flush so the object gets an identity.
        if session.in_transaction():
            session.flush()
        else:
            session.commit()
        session.refresh(seq)
    return seq

def peek_next_sequence(session: Session, name: str) -> int:
    """Regarde la prochaine valeur (sans la consommer)."""
    return _get_seq(session, name).value + 1

def get_next_sequence(session: Session, name: str) -> int:
    """Incrémente et retourne la nouvelle valeur de la séquence `name`."""
    seq = _get_seq(session, name)
    seq.value += 1
    session.add(seq)
    if session.in_transaction():
        session.flush()
    else:
        session.commit()
    return seq.value


# Convert common ISO datetime strings to datetime objects before flush

def _coerce_datetime_value(v):
    if isinstance(v, str):
        # Try ISO formats
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(v, fmt)
            except Exception:
                continue
        # Solution de repli: try to parse first 14 digits as YYYYMMDDHHMMSS
        s = ''.join([c for c in v if c.isdigit()])
        try:
            return datetime.strptime(s[:14], "%Y%m%d%H%M%S")
        except Exception:
            return v
    return v


def _before_flush(session, flush_context, instances):
    """Normalise quelques attributs date/heure si fournis comme chaînes.

    Ceci permet d'accepter des formats ISO usuels ou des timestamps HL7-like (YYYYMMDDHHMMSS)
    sans faire échouer la persistance. Les attributs visés: admit_time, discharge_time,
    start_time, when, created_at, updated_at.
    """
    for obj in list(session.new) + list(session.dirty):
        # Auto-assign a dossier_seq when creating a Dossier without one.
        # Many unit tests create a Dossier without providing dossier_seq; the
        # DB model requires it. To keep tests simple and avoid introducing
        # commits inside before_flush we increment the Sequence object
        # manually here so the value will be flushed with the current
        # transaction.
        if isinstance(obj, Dossier):
            # Only assign if absent or falsy
            if getattr(obj, "dossier_seq", None) in (None, 0):
                # Try to get existing Sequence row; if missing, create it.
                seq = session.get(Sequence, "dossier")
                if not seq:
                    seq = Sequence(name="dossier", value=0)
                    session.add(seq)
                    # Do not commit here; let the surrounding flush handle persistence.
                # Increment and assign
                seq.value = (seq.value or 0) + 1
                obj.dossier_seq = seq.value

        # Backwards-compat: support legacy field names used in older tests/scripts
        # Mouvement legacy fields: date_heure_mouvement -> when, type_mouvement -> movement_type
        if isinstance(obj, Mouvement):
            # date_heure_mouvement may be provided by older tests
            if getattr(obj, "date_heure_mouvement", None) is not None and getattr(obj, "when", None) is None:
                try:
                    obj.when = getattr(obj, "date_heure_mouvement")
                except Exception as exc:
                    logger.debug("Optional operation skipped", exc_info=exc)
            # type_mouvement -> movement_type
            if getattr(obj, "type_mouvement", None) is not None and getattr(obj, "movement_type", None) is None:
                try:
                    obj.movement_type = getattr(obj, "type_mouvement")
                except Exception as exc:
                    logger.debug("Optional operation skipped", exc_info=exc)
        # Venue legacy 'statut' -> operational_status
        if isinstance(obj, Venue):
            if getattr(obj, "statut", None) is not None and getattr(obj, "operational_status", None) is None:
                try:
                    obj.operational_status = getattr(obj, "statut")
                except Exception as exc:
                    logger.debug("Optional operation skipped", exc_info=exc)
        # handle a few common datetime-like attributes
        for attr in ("admit_time", "discharge_time", "start_time", "when", "created_at", "updated_at"):
            if hasattr(obj, attr):
                v = getattr(obj, attr)
                new_v = _coerce_datetime_value(v)
                if new_v is not None and new_v is not v:
                    setattr(obj, attr, new_v)

        # Normalize list-like attributes that are stored as CSV in DB (e.g. tags)
        if hasattr(obj, "tags"):
            tags_val = getattr(obj, "tags")
            if isinstance(tags_val, (list, tuple)):
                try:
                    setattr(obj, "tags", ",".join(str(x) for x in tags_val))
                except Exception as exc:
                    logger.debug("Optional operation skipped", exc_info=exc)
                # Map legacy finess_eg -> finess for EntiteGeographique
                if isinstance(obj, EntiteGeographique):
                    if getattr(obj, "finess", None) in (None, "") and getattr(obj, "finess_eg", None):
                        obj.finess = getattr(obj, "finess_eg")
    # Handle cascade-like deletion for tests: if a Dossier is deleted in the session,
    # ensure its Venue and Mouvement children are also deleted to respect tests' expectations.
    # We perform this here because the DB schema may not have ON DELETE CASCADE in tests
    # (in-memory schemas are created per test), so we emulate cascade to avoid FK errors.
    deleted = list(session.deleted)
    for obj in deleted:
        if isinstance(obj, Dossier):
            # Find and delete child venues and mouvements
            try:
                venues = session.exec(select(Venue).where(Venue.dossier_id == obj.id)).all()
                for v in venues:
                    mvts = session.exec(select(Mouvement).where(Mouvement.venue_id == v.id)).all()
                    for m in mvts:
                        session.delete(m)
                    session.delete(v)
            except Exception:
                # If select fails (models not loaded), skip
                continue


event.listen(Session, "before_flush", _before_flush)


def get_db_health() -> dict:
    """Vérifie la santé de la base de données et retourne les métriques."""
    try:
        with Session(engine) as session:
            # Test de connexion simple
            result = session.execute(text("SELECT 1"))
            result.scalar()

            # Récupérer des métriques SQLite si applicable
            metrics = {"status": "healthy", "connection": "ok"}

            if engine.dialect.name == "sqlite":
                try:
                    # Interroger la connexion SQLAlchemy réellement configurée. Ouvrir
                    # un fichier SQLite codé en dur faussait l'état en test et avec une
                    # URL de base différente.
                    pragmas = {
                        "journal_mode": "journal_mode",
                        "synchronous": "synchronous",
                        "cache_size_kb": "cache_size",
                        "page_count": "page_count",
                        "page_size": "page_size",
                    }
                    for metric, pragma in pragmas.items():
                        metrics[metric] = session.execute(text(f"PRAGMA {pragma}")).scalar()
                except Exception as e:
                    metrics["sqlite_metrics_error"] = str(e)

            return metrics

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def optimize_db_connection():
    """Optimise la connexion à la base de données (appelable manuellement)."""
    try:
        with engine.connect() as conn:
            # Test de la connexion
            conn.execute(text("SELECT 1"))
            logger.info("Connexion à la base de données optimisée")
    except Exception as e:
        logger.warning("Erreur lors de l'optimisation de la connexion DB: %s", e)
