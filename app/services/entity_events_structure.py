"""Automatic emissions for structure entities (EG, Pole, Service, UF, UH, Chambre, Lit).

This registers SQLAlchemy event listeners to detect insert/update/delete on
structure models and emit structure notifications (FHIR Location and HL7 MFN)
after transaction commit, for all sources (UI, HL7 importers, scripts).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, Set, Tuple

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models_structure import (
    EntiteGeographique,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
    Chambre,
    Lit,
)
from app.models_structure import EntiteJuridique
from app.services.structure_emit import emit_structure_change, emit_structure_delete

logger = logging.getLogger(__name__)

# Track pending emissions per SQLAlchemy Session
# Format: (model_name, entity_id, op, frozen_metadata)
_pending: Dict[int, Set[Tuple[str, int, str, tuple]]] = {}

# Re-entrancy guard for emissions
_emitting_flag = threading.local()

# Limit concurrency of background emissions
_sem = asyncio.Semaphore(1)


def _sess_id(session: Session) -> int:
    return id(session)


def _schedule(session: Session, model_name: str, entity_id: int, op: str, metadata: Dict[str, Any] = None) -> None:
    if getattr(_emitting_flag, "active", False):
        logger.debug("[structure_events] Skip during emission: %s id=%s op=%s", model_name, entity_id, op)
        return
    sid = _sess_id(session)
    if sid not in _pending:
        _pending[sid] = set()
    # Convert metadata dict to hashable tuple
    frozen_metadata = tuple(sorted((metadata or {}).items()))
    key = (model_name, entity_id, op, frozen_metadata)
    _pending[sid].add(key)
    logger.debug("[structure_events] Scheduled %s id=%s op=%s", model_name, entity_id, op)


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session):
    sid = _sess_id(session)
    items = _pending.pop(sid, None)
    if not items:
        return
    logger.info("[structure_events] Processing %d structure emission(s)", len(items))
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop available, skip (e.g., scripts without async loop)
        logger.warning("[structure_events] No event loop; skipping emissions")
        return
    for model_name, entity_id, op, frozen_metadata in items:
        # Convert frozen metadata back to dict
        metadata = dict(frozen_metadata) if frozen_metadata else {}
        loop.create_task(_emit_background(model_name, entity_id, op, metadata))


async def _emit_background(model_name: str, entity_id: int, op: str, metadata: Dict[str, Any]):

    from app.db import engine
    from sqlmodel import Session as SQLModelSession
    from app.models_structure import (
        EntiteGeographique,
        Pole,
        Service,
        UniteFonctionnelle,
        UniteHebergement,
        Chambre,
        Lit,
    )
    from app.models_structure import EntiteJuridique
    import asyncio
    import time

    model_map = {
        "EntiteJuridique": EntiteJuridique,
        "EntiteGeographique": EntiteGeographique,
        "Pole": Pole,
        "Service": Service,
        "UniteFonctionnelle": UniteFonctionnelle,
        "UniteHebergement": UniteHebergement,
        "Chambre": Chambre,
        "Lit": Lit,
    }

    model = model_map.get(model_name)
    if not model:
        return

    max_attempts = 3
    base_delay = 2.0
    attempt = 0
    async with _sem:
        _emitting_flag.active = True
        while attempt < max_attempts:
            try:
                with SQLModelSession(engine) as s:
                    if op == "delete":
                        await emit_structure_delete(entity_id, s, entity_type=model_name, **metadata)
                    else:
                        entity = s.get(model, entity_id)
                        if not entity:
                            logger.warning("[structure_events] %s id=%s not found for op=%s", model_name, entity_id, op)
                            return
                        # Transmet le GHT associé si présent
                        ght_context_id = getattr(entity, 'ght_context_id', None)
                        await emit_structure_change(entity, s, operation=op, ght_context_id=ght_context_id)
                break  # Success, exit loop
            except Exception as exc:
                attempt += 1
                logger.error(
                    f"[structure_events] Emission failed for {model_name} id={entity_id} op={op} (attempt {attempt}/{max_attempts}): {exc}",
                    exc_info=True
                )
                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(f"[structure_events] Retry in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[structure_events] Max attempts reached for {model_name} id={entity_id} op={op}. Giving up.")
        _emitting_flag.active = False


def _after_insert(mapper, connection, target):
    session = Session.object_session(target)
    if not session:
        return
    _schedule(session, type(target).__name__, target.id, "insert")


def _after_update(mapper, connection, target):
    session = Session.object_session(target)
    if not session:
        return
    _schedule(session, type(target).__name__, target.id, "update")


def _after_delete(mapper, connection, target):
    session = Session.object_session(target)
    if not session:
        return
    # id is still available on target in after_delete
    # For EntiteJuridique, capture finess_ej for delete emission
    metadata = {}
    from app.models_structure import EntiteJuridique
    if isinstance(target, EntiteJuridique):
        metadata["finess_ej"] = target.finess_ej
    _schedule(session, type(target).__name__, target.id, "delete", metadata)


def register_structure_entity_events() -> None:
    """Register SQLAlchemy listeners for structure models."""
    for model in (EntiteJuridique, EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit):
        event.listen(model, "after_insert", _after_insert)
        event.listen(model, "after_update", _after_update)
        event.listen(model, "after_delete", _after_delete)
    logger.info("[structure_events] ✓ Listeners registered for structure models (including EntiteJuridique)")
