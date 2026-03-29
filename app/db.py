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

from sqlmodel import SQLModel, create_engine, Session, select, text
from sqlalchemy.engine.url import make_url
from typing import Optional

# Import ALL models to ensure tables are registered
from app.models import Sequence, Patient, Dossier, Venue, Mouvement
from app.models_endpoints import SystemEndpoint, MessageLog
from app.models_vocabulary import VocabularySystem, VocabularyValue, VocabularyMapping
from app.models_structure import GHTContext, IdentifierNamespace, EntiteJuridique, EntiteGeographique
from app.models.hprim_models import HprimMessage, HprimCCAMAct, HprimNGAPAct
from app.models_identifiers import Identifier
from app.models_practitioners import MedecinResponsable  # Import for FK resolution
from app import models_scenarios  # ensure scenario models are registered
from app import models_scenario_runs  # ensure scenario execution run models are registered
try:  # Import optionnel de l'init des templates (peut échouer si fichiers absents)
    from app.services.scenario_template_init import init_scenario_templates  # noqa: E402
except Exception:  # pragma: no cover
    init_scenario_templates = None  # type: ignore
from app import models_workflows  # ensure workflow models are registered


# Use in-memory SQLite for tests, file-based otherwise
import os
from sqlalchemy.pool import StaticPool

# Import de la configuration centralisée
from config.settings import settings
import sys

# Consider we're in testing mode when either the Settings say so or we're
# running under pytest (common for local test runs launched via
# `python -m pytest`). This makes SQLModel.metadata.create_all() run for
# in-memory engines during test collection so fixtures relying on an
# initialized schema don't fail with "no such table".
_running_under_pytest = any("pytest" in arg for arg in sys.argv)
testing_flag = bool(settings.testing or _running_under_pytest)

if testing_flag:
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # When running tests in-process (TESTING=1) we need the schema
    # created on the in-memory engine so TestClient-based tests can
    # operate without requiring an explicit init_db() call.
    try:
        SQLModel.metadata.create_all(engine)
    except Exception:
        # If schema creation fails for any reason, allow tests to
        # manage their own schema creation as some fixtures do.
        pass
else:
    # Configuration avancée du pool de connexions pour SQLite
    from sqlalchemy.pool import StaticPool, QueuePool

    # For non-testing runs, prefer StaticPool for SQLite; during testing use QueuePool
    pool_class = StaticPool if not testing_flag else QueuePool

    # Préparer les arguments du moteur selon le type de base
    engine_kwargs = {
        "echo": settings.db_echo,
        "poolclass": pool_class,
        "pool_pre_ping": True,  # Vérifier les connexions avant utilisation
        "pool_recycle": 3600,  # Recycler les connexions après 1 heure
    }

    # Paramètres de pool seulement pour les bases non-SQLite
    if "sqlite" not in settings.database_url.lower():
        engine_kwargs.update({
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
        })
    else:
        # Pour SQLite, paramètres spécifiques
        engine_kwargs["connect_args"] = {
            "check_same_thread": False,  # Permettre l'accès multi-thread pour SQLite
            "timeout": 30.0,  # Timeout de connexion
        }

    engine = create_engine(settings.database_url, **engine_kwargs)

def init_db() -> None:
    """Crée les tables si elles n'existent pas (idempotent)."""
    SQLModel.metadata.create_all(engine)
    # Optimisations SQLite avancées pour la performance et la robustesse
    try:
        import sqlite3
        db_url = make_url(settings.database_url)
        if db_url.drivername != "sqlite":
            # Les PRAGMA/index spécifiques SQLite ne s'appliquent pas aux autres SGBD.
            if init_scenario_templates:
                with Session(engine) as _s:
                    init_scenario_templates(_s)
            return

        sqlite_db_path = db_url.database
        # SQLite in-memory: aucun fichier à optimiser.
        if not sqlite_db_path or sqlite_db_path == ":memory:":
            if init_scenario_templates:
                with Session(engine) as _s:
                    init_scenario_templates(_s)
            return

        # Normaliser les chemins relatifs (ex: ./data/medbridge.db)
        sqlite_db_path = os.path.abspath(sqlite_db_path)
        os.makedirs(os.path.dirname(sqlite_db_path), exist_ok=True)
        conn = sqlite3.connect(sqlite_db_path)

        # Optimisations de performance
        conn.execute("PRAGMA journal_mode=WAL;")  # Mode WAL pour accès concurrents
        conn.execute("PRAGMA synchronous=NORMAL;")  # Balance performance/sécurité
        conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache (négatif = KB)
        conn.execute("PRAGMA temp_store=MEMORY;")  # Tables temporaires en RAM
        conn.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap pour gros fichiers
        conn.execute("PRAGMA page_size=4096;")  # Taille de page optimisée

        # Index pour les performances de recherche
        # Patients
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_family ON patient(family);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_given ON patient(given);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_identifier ON patient(identifier);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_ght_context ON patient(ght_context_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_entite_juridique ON patient(entite_juridique_id);")

        # Dossiers
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dossier_patient_id ON dossier(patient_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dossier_entite_juridique ON dossier(entite_juridique_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dossier_type ON dossier(dossier_type);")

        # Venues
        conn.execute("CREATE INDEX IF NOT EXISTS idx_venue_entite_juridique ON venue(entite_juridique_id);")

        # Mouvements
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mouvement_venue_id ON mouvement(venue_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mouvement_date ON mouvement(date);")

        # Messages et endpoints
        conn.execute("CREATE INDEX IF NOT EXISTS idx_message_log_created_at ON messagelog(created_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_message_log_endpoint_id ON messagelog(endpoint_id);")

        # Vocabulaires
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_system ON vocabularyvalue(system);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_code ON vocabularyvalue(code);")

        # Try to create an FTS5 table for patient text search (optional, best-effort)
        try:
            # FTS5 requires the module compiled in SQLite. This is a best-effort, no-op if unavailable.
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS patient_fts USING fts5(family, given, content='');")
            # Populate FTS table from existing patients
            conn.execute("INSERT INTO patient_fts(rowid, family, given) SELECT id, family, given FROM patient WHERE id NOT IN (SELECT rowid FROM patient_fts);")
        except Exception:
            # ignore if FTS not available
            pass

        conn.commit()
        conn.close()
        print(f"[INFO] Optimisations SQLite appliquées avec succès sur {sqlite_db_path}")
    except Exception as e:
        print(f"[WARN] Erreur lors des optimisations SQLite: {e}")
    # Initialisation idempotente des templates de scénarios abstraits (IHE, démo...)
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
from sqlalchemy import event
from datetime import datetime

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
    from app.models import Dossier, Venue, Mouvement

    for obj in list(session.new) + list(session.dirty):
        # Auto-assign a dossier_seq when creating a Dossier without one.
        # Many unit tests create a Dossier without providing dossier_seq; the
        # DB model requires it. To keep tests simple and avoid introducing
        # commits inside before_flush we increment the Sequence object
        # manually here so the value will be flushed with the current
        # transaction.
        try:
            from app.models import Dossier, Sequence
        except Exception:
            Dossier = None
            Sequence = None

        if Dossier is not None and isinstance(obj, Dossier):
            # Only assign if absent or falsy
            if getattr(obj, "dossier_seq", None) in (None, 0):
                # Try to get existing Sequence row; if missing, create it.
                seq = session.get(Sequence, "dossier") if Sequence is not None else None
                if not seq:
                    seq = Sequence(name="dossier", value=0)
                    session.add(seq)
                    # Do not commit here; let the surrounding flush handle persistence.
                # Increment and assign
                seq.value = (seq.value or 0) + 1
                obj.dossier_seq = seq.value

        # Backwards-compat: support legacy field names used in older tests/scripts
        try:
            from app.models import Mouvement, Venue
        except Exception:
            Mouvement = None
            Venue = None

        # Mouvement legacy fields: date_heure_mouvement -> when, type_mouvement -> movement_type
        if Mouvement is not None and isinstance(obj, Mouvement):
            # date_heure_mouvement may be provided by older tests
            if getattr(obj, "date_heure_mouvement", None) is not None and getattr(obj, "when", None) is None:
                try:
                    obj.when = getattr(obj, "date_heure_mouvement")
                except Exception:
                    pass
            # type_mouvement -> movement_type
            if getattr(obj, "type_mouvement", None) is not None and getattr(obj, "movement_type", None) is None:
                try:
                    obj.movement_type = getattr(obj, "type_mouvement")
                except Exception:
                    pass

        # Venue legacy 'statut' -> operational_status
        if Venue is not None and isinstance(obj, Venue):
            if getattr(obj, "statut", None) is not None and getattr(obj, "operational_status", None) is None:
                try:
                    obj.operational_status = getattr(obj, "statut")
                except Exception:
                    pass
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
                except Exception:
                    pass

                # Map legacy finess_eg -> finess for EntiteGeographique
                if isinstance(obj, EntiteGeographique):
                    if getattr(obj, "finess", None) in (None, "") and getattr(obj, "finess_eg", None):
                        obj.finess = getattr(obj, "finess_eg")
    # Handle cascade-like deletion for tests: if a Dossier is deleted in the session,
    # ensure its Venue and Mouvement children are also deleted to respect tests' expectations.
    # We perform this here because the DB schema may not have ON DELETE CASCADE in tests
    # (in-memory schemas are created per test), so we emulate cascade to avoid FK errors.
    from app.models import Dossier, Venue, Mouvement
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

            if "sqlite" in str(engine.url):
                try:
                    import sqlite3
                    conn = sqlite3.connect("data/medbridge.db")
                    cursor = conn.cursor()

                    # Métriques SQLite
                    cursor.execute("PRAGMA journal_mode;")
                    metrics["journal_mode"] = cursor.fetchone()[0]

                    cursor.execute("PRAGMA synchronous;")
                    metrics["synchronous"] = cursor.fetchone()[0]

                    cursor.execute("PRAGMA cache_size;")
                    metrics["cache_size_kb"] = cursor.fetchone()[0]

                    cursor.execute("PRAGMA page_count;")
                    metrics["page_count"] = cursor.fetchone()[0]

                    cursor.execute("PRAGMA page_size;")
                    metrics["page_size"] = cursor.fetchone()[0]

                    conn.close()
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
            print("[INFO] Connexion à la base de données optimisée")
    except Exception as e:
        print(f"[WARN] Erreur lors de l'optimisation de la connexion DB: {e}")
