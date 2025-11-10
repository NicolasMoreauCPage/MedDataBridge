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

from sqlmodel import SQLModel, create_engine, Session, select
from typing import Optional

# Import ALL models to ensure tables are registered
from app.models import Sequence, Patient, Dossier, Venue, Mouvement
from app.models_endpoints import SystemEndpoint, MessageLog
from app.models_vocabulary import VocabularySystem, VocabularyValue, VocabularyMapping
from app.models_structure_fhir import GHTContext, IdentifierNamespace
from app.models_structure import EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.models_identifiers import Identifier
from app import models_scenarios  # ensure scenario models are registered
try:  # Import optionnel de l'init des templates (peut échouer si fichiers absents)
    from app.services.scenario_template_init import init_scenario_templates  # noqa: E402
except Exception:  # pragma: no cover
    init_scenario_templates = None  # type: ignore
from app import models_workflows  # ensure workflow models are registered

# Moteur SQLite local. Par défaut, fichier `medbridge.db` au répertoire courant.
# Pool size increased to handle concurrent emissions
engine = create_engine(
    "sqlite:///./medbridge.db",
    echo=False,
    pool_size=20,  # Increased from default 5
    max_overflow=30,  # Increased from default 10
    pool_timeout=60,  # Increased from default 30
    pool_pre_ping=True  # Check connections before using
)

def init_db() -> None:
    """Crée les tables si elles n'existent pas (idempotent)."""
    SQLModel.metadata.create_all(engine)
    # Initialisation idempotente des templates de scénarios abstraits (IHE, démo...)
    if init_scenario_templates:
        with Session(engine) as _s:
            init_scenario_templates(_s)

def get_session():
    """Dépendance FastAPI: fournit une session courte (context manager)."""
    with Session(engine) as session:
        yield session

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
        # fallback: try to parse first 14 digits as YYYYMMDDHHMMSS
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
