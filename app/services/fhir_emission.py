"""Responsabilités FHIR extraites de l'émetteur multi-protocole.

Ce module ne transporte rien : il prépare le Bundle, résout les cibles et
persiste la reprise. L'appel HTTP reste volontairement au niveau de
``emit_on_create`` pour préserver les points de monkeypatch des tests.
"""

import asyncio
import concurrent.futures
import inspect
import json
import logging
import time
from datetime import datetime
from typing import Callable, Literal, Sequence

from sqlmodel import Session, select

from app.models_endpoints import FHIRConfig, MessageLog, SystemEndpoint
from app.metrics import record_outbound_delivery_safely
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


def _resolve_transport_result(result: object) -> object:
    """Résout un transport FHIR asynchrone, même depuis une boucle active."""
    if not inspect.iscoroutine(result):
        return result
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(result)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, result).result(timeout=12)


def _upsert_fhir_log(
    session: Session,
    *,
    endpoint: SystemEndpoint,
    correlation_id: str | None,
    payload: str,
    acknowledgment: str,
    status: str,
) -> MessageLog:
    """Conserve un seul journal FHIR par corrélation ou reprise ouverte."""
    if correlation_id:
        existing = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint.id)
            .where(MessageLog.direction == "out")
            .where(MessageLog.correlation_id == correlation_id)
        ).first()
    else:
        existing = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint.id)
            .where(MessageLog.kind == "FHIR")
            .where(MessageLog.status.in_(["error", "pending"]))
            .order_by(MessageLog.created_at.desc())
        ).first()

    if existing:
        existing.payload = payload
        existing.ack_payload = acknowledgment
        existing.status = status
        existing.created_at = datetime.utcnow()
        log = existing
    else:
        log = MessageLog(
            direction="out",
            kind="FHIR",
            endpoint_id=endpoint.id,
            payload=payload,
            ack_payload=acknowledgment,
            status=status,
            correlation_id=correlation_id,
        )
        session.add(log)
    session.commit()
    return log


def emit_fhir_payload(
    session: Session,
    *,
    endpoint: SystemEndpoint,
    payload: object,
    correlation_id: str | None,
    sender: Callable[..., object] | None = None,
) -> MessageLog:
    """Livre un Bundle FHIR une fois puis délègue les reprises à l'outbox.

    La génération, le journal, le transport et la reprise sont ainsi regroupés
    hors de l'orchestrateur multi-protocole. Le Bundle sérialisé est le même
    dans le journal et dans l'outbox durable.
    """
    started_at = time.monotonic()
    payload_text = json.dumps(payload, default=str)
    targets = build_fhir_targets(endpoint)
    if not targets:
        message_log = _upsert_fhir_log(
            session,
            endpoint=endpoint,
            correlation_id=correlation_id,
            payload=payload_text,
            acknowledgment="Endpoint FHIR non configuré",
            status="error",
        )
        logger.warning(
            "FHIR outbound delivery skipped because no target is configured endpoint=%s correlation_id=%s",
            endpoint.id,
            correlation_id,
        )
        record_outbound_delivery_safely(
            protocol="FHIR",
            status="error",
            duration_seconds=time.monotonic() - started_at,
            endpoint_id=endpoint.id,
            correlation_id=correlation_id,
            error_type="MISSING_TARGET",
        )
        return message_log

    if sender is None:
        from app.services.fhir_transport import post_fhir_bundle

        sender = post_fhir_bundle

    last_log: MessageLog | None = None
    for base_url, auth_kind, auth_token in targets:
        started_at = time.monotonic()
        error_type: str | None = None
        try:
            status_code, response_body = _resolve_transport_result(
                sender(base_url, payload, auth_kind=auth_kind, auth_token=auth_token)
            )
            status = "sent" if 200 <= status_code < 300 else "error"
            acknowledgment = json.dumps(response_body or {}, default=str)
            if status == "error":
                error_type = "HTTP_STATUS"
                logger.warning(
                    "FHIR outbound delivery returned a non-success status endpoint=%s correlation_id=%s status_code=%s",
                    endpoint.id,
                    correlation_id,
                    status_code,
                )
        except Exception as exc:
            status = "error"
            acknowledgment = str(exc)
            error_type = type(exc).__name__
            logger.warning(
                "FHIR outbound delivery failed endpoint=%s correlation_id=%s error_type=%s",
                endpoint.id,
                correlation_id,
                error_type,
                exc_info=True,
            )

        last_log = _upsert_fhir_log(
            session,
            endpoint=endpoint,
            correlation_id=correlation_id,
            payload=payload_text,
            acknowledgment=acknowledgment,
            status=status,
        )
        record_outbound_delivery_safely(
            protocol="FHIR",
            status=status,
            duration_seconds=time.monotonic() - started_at,
            endpoint_id=endpoint.id,
            correlation_id=correlation_id,
            error_type=error_type,
        )
        if status == "sent":
            return last_log

    if last_log is not None:
        queue_fhir_retry(session, endpoint, payload_text, correlation_id, last_log)
    return last_log
