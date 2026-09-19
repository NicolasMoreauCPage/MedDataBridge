"""Responsabilités FHIR extraites de l'émetteur multi-protocole.

Ce module ne transporte rien : il prépare le Bundle, résout les cibles et
persiste la reprise. L'appel HTTP reste volontairement au niveau de
``emit_on_create`` pour préserver les points de monkeypatch des tests.
"""

import logging
from typing import Literal, Sequence

from sqlmodel import Session

from app.models_endpoints import FHIRConfig, MessageLog, SystemEndpoint
from app.services.fhir_resources import generate_fhir_bundle_for_entity
from app.services.outbox_service import enqueue_message


logger = logging.getLogger(__name__)


def generate_fhir(
    entity,
    entity_type: Literal["patient", "dossier", "venue", "mouvement"],
    session: Session,
    forced_identifier_system: str | None = None,
    forced_identifier_oid: str | None = None,
):
    """Construit le Bundle FHIR de l'entité à émettre."""
    return generate_fhir_bundle_for_entity(entity, entity_type, session)


def build_fhir_targets(
    endpoint: SystemEndpoint,
) -> Sequence[tuple[str, str, str | None]]:
    """Résout les cibles FHIR, y compris le réglage historique ``base_url``."""
    targets = [
        (config.base_url, config.auth_kind or "none", config.auth_token)
        for config in (getattr(endpoint, "fhir_configs", []) or [])
        if isinstance(config, FHIRConfig) and config.is_enabled and config.base_url
    ]
    if targets:
        return targets
    if getattr(endpoint, "base_url", None):
        return [(
            endpoint.base_url,
            getattr(endpoint, "auth_kind", None) or "none",
            getattr(endpoint, "auth_token", None),
        )]

    host = (endpoint.host or "").strip()
    if not host:
        return []
    if host.startswith(("http://", "https://")):
        base_url = host
        if endpoint.port and ":" not in host.split("//", 1)[1]:
            base_url = f"{host}:{endpoint.port}"
    else:
        scheme = "https" if str(endpoint.port) in {"443", "8443"} else "http"
        base_url = f"{scheme}://{host}"
        if endpoint.port:
            base_url = f"{base_url}:{endpoint.port}"
    return [(base_url, "none", None)]


def queue_fhir_retry(
    session: Session,
    endpoint: SystemEndpoint,
    payload: str,
    correlation_id: str | None,
    message_log: MessageLog,
) -> None:
    """Confie une reprise FHIR à l'outbox durable, sans attente bloquante."""
    if message_log.id is None:
        session.flush()
    queued = enqueue_message(
        session,
        endpoint_id=endpoint.id,
        protocol="FHIR",
        payload=payload,
        correlation_id=correlation_id,
        source_message_log_id=message_log.id,
    )
    # Une reprise ouverte est idempotente : le Bundle durable est celui qui
    # sera réellement rejoué. Ne pas laisser un nouveau Bundle (et son
    # timestamp) remplacer seulement le journal, sinon l'audit diverge de
    # l'outbox sans que le transport ne puisse jamais l'envoyer.
    if queued.payload != payload:
        message_log.payload = queued.payload
        session.add(message_log)
    session.commit()
    logger.info(
        "FHIR emission queued for durable retry endpoint=%s outbox_id=%s correlation_id=%s",
        endpoint.id,
        queued.id,
        correlation_id,
    )
