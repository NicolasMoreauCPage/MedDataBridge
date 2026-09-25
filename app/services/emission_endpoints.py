"""Sélection résiliente des destinations d'émission.

Ce module isole l'accès aux endpoints de l'orchestrateur historique afin que
la génération des payloads et le transport puissent être testés séparément.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlmodel import Session, select

from app.models.endpoints import SystemEndpoint

logger = logging.getLogger(__name__)


def list_eligible_sender_endpoints(
    session: Session,
    entity: object,
    *,
    max_retries: int = 3,
) -> list[SystemEndpoint]:
    """Retourne les destinations globales ou rattachées au contexte de l'entité.

    Les rares contentions SQLite sont réessayées avec un court backoff. Aucun
    transport réseau n'est réalisé ici : les reprises de livraison relèvent de
    l'outbox durable.
    """
    endpoints: Iterable[SystemEndpoint] | None = None
    for attempt in range(max_retries):
        try:
            endpoints = session.exec(
                select(SystemEndpoint)
                .where(SystemEndpoint.role.in_(["sender", "both"]))
                .where(SystemEndpoint.is_enabled.is_(True))
            ).all()
            break
        except (InterfaceError, OperationalError) as exc:
            message = str(exc).lower()
            retryable = "locked" in message or "out of sequence" in message
            if not retryable or attempt == max_retries - 1:
                raise
            session.rollback()
            time.sleep(0.1 * (2**attempt))

    entity_ej_id = getattr(entity, "entite_juridique_id", None)
    entity_ght_id = getattr(entity, "ght_context_id", None)
    return [
        endpoint
        for endpoint in endpoints or []
        if (
            (
                getattr(endpoint, "entite_juridique_id", None) is None
                and getattr(endpoint, "ght_context_id", None) is None
            )
            or (
                entity_ej_id is not None
                and getattr(endpoint, "entite_juridique_id", None) == entity_ej_id
            )
            or (
                entity_ght_id is not None
                and getattr(endpoint, "ght_context_id", None) == entity_ght_id
            )
        )
    ]
