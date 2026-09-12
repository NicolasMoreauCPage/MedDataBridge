"""Gestion de l'outbox durable des transports sortants.

Le worker est volontairement appelable à la demande (route API ou tâche planifiée)
afin de ne pas imposer de processus supplémentaire sur les installations LAN.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.fhir_transport import post_fhir_bundle
from app.services.mllp import send_mllp


def enqueue_message(
    session: Session,
    *,
    endpoint_id: int,
    protocol: str,
    payload: str,
    message_type: Optional[str] = None,
    correlation_id: Optional[str] = None,
    source_message_log_id: Optional[int] = None,
    max_attempts: int = 8,
) -> OutboundMessage:
    """Ajoute un message, sans dupliquer une reprise déjà ouverte du même log."""
    if source_message_log_id:
        existing = session.exec(
            select(OutboundMessage)
            .where(OutboundMessage.source_message_log_id == source_message_log_id)
            .where(OutboundMessage.status.in_(["pending", "retry"]))
        ).first()
        if existing:
            return existing
    row = OutboundMessage(
        endpoint_id=endpoint_id,
        protocol=protocol.upper(),
        payload=payload,
        message_type=message_type,
        correlation_id=correlation_id,
        source_message_log_id=source_message_log_id,
        max_attempts=max_attempts,
    )
    session.add(row)
    return row


def enqueue_failed_message_logs(session: Session) -> int:
    """Transforme les échecs persistés des émetteurs historiques en reprises durables."""
    logs = session.exec(
        select(MessageLog)
        .where(MessageLog.direction == "out")
        .where(MessageLog.status.in_(["error", "pending", "ack_error"]))
        .where(MessageLog.endpoint_id.is_not(None))
    ).all()
    created = 0
    for log in logs:
        before = session.exec(
            select(OutboundMessage)
            .where(OutboundMessage.source_message_log_id == log.id)
            .where(OutboundMessage.status.in_(["pending", "retry"]))
        ).first()
        if before is None:
            enqueue_message(
                session,
                endpoint_id=log.endpoint_id,
                protocol=log.kind,
                payload=log.payload,
                message_type=log.message_type,
                correlation_id=log.correlation_id,
                source_message_log_id=log.id,
            )
            created += 1
    return created


def retry_now(session: Session, outbox_id: int) -> OutboundMessage:
    row = session.get(OutboundMessage, outbox_id)
    if row is None:
        raise ValueError("Message d'outbox introuvable")
    row.status = "pending"
    row.attempts = 0
    row.last_error = None
    row.next_attempt_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    session.add(row)
    return row


async def process_due_messages(session: Session, limit: int = 100) -> dict:
    """Envoie les lignes échues et applique un backoff exponentiel borné."""
    now = datetime.utcnow()
    rows = session.exec(
        select(OutboundMessage)
        .where(OutboundMessage.status.in_(["pending", "retry"]))
        .where(OutboundMessage.next_attempt_at <= now)
        .order_by(OutboundMessage.next_attempt_at)
        .limit(limit)
    ).all()
    result = {"processed": 0, "sent": 0, "retry": 0, "failed": 0}
    for row in rows:
        result["processed"] += 1
        endpoint = session.get(SystemEndpoint, row.endpoint_id)
        try:
            if not endpoint or not endpoint.is_enabled:
                raise ValueError("Endpoint indisponible ou désactivé")
            if row.protocol == "MLLP":
                if not endpoint.host or not endpoint.port:
                    raise ValueError("Endpoint MLLP incomplet (host/port)")
                ack = await send_mllp(endpoint.host, endpoint.port, row.payload)
                if "MSA|AE|" in ack or "MSA|AR|" in ack:
                    raise ValueError(f"ACK négatif: {ack[:300]}")
            elif row.protocol == "FHIR":
                if not endpoint.base_url:
                    raise ValueError("Endpoint FHIR sans base_url")
                payload = json.loads(row.payload)
                status_code, response = await post_fhir_bundle(endpoint.base_url, payload, endpoint.auth_kind or "none", endpoint.auth_token)
                if not 200 <= status_code < 300:
                    raise ValueError(f"FHIR HTTP {status_code}: {json.dumps(response, ensure_ascii=False)[:300]}")
                ack = json.dumps(response, ensure_ascii=False)
            else:
                raise ValueError(f"Protocole d'outbox non supporté: {row.protocol}")

            row.status, row.sent_at, row.last_error = "sent", now, None
            if row.source_message_log_id:
                log = session.get(MessageLog, row.source_message_log_id)
                if log:
                    log.status, log.ack_payload = "sent", ack
                    session.add(log)
            result["sent"] += 1
        except Exception as exc:  # noqa: BLE001
            row.attempts += 1
            row.last_error = str(exc)[:1000]
            if row.attempts >= row.max_attempts:
                row.status = "failed"
                result["failed"] += 1
            else:
                row.status = "retry"
                row.next_attempt_at = now + timedelta(seconds=min(3600, 2 ** row.attempts))
                result["retry"] += 1
        row.updated_at = now
        session.add(row)
    session.commit()
    return result
