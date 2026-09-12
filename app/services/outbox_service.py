"""Gestion de l'outbox durable des transports sortants.

Le worker est volontairement appelable à la demande (route API ou tâche planifiée)
afin de ne pas imposer de processus supplémentaire sur les installations LAN.
"""

import asyncio
import json
from datetime import datetime, timedelta
from ftplib import FTP
from io import BytesIO
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.models_endpoints import FHIRConfig, MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.fhir_transport import post_fhir_bundle
from app.services.mllp import send_mllp


def _outbox_suffix(message_type: Optional[str]) -> str:
    normalized = (message_type or "").upper()
    if normalized.startswith("HPRIM"):
        return ".xml"
    if normalized.lower() in {"fhir", "json", "bundle"}:
        return ".json"
    return ".hl7"


def _send_sftp(endpoint: SystemEndpoint, filename: str, payload: str) -> None:
    from app.adapters.sftp_writer import SFTPWriter
    writer = SFTPWriter(
        host=endpoint.ftp_host or "",
        port=endpoint.ftp_port or 22,
        username=endpoint.ftp_username,
        password=endpoint.ftp_password,
        remote_path=endpoint.ftp_remote_outbox_path or ".",
    )
    try:
        writer.connect()
        writer.write_file(filename, payload)
    finally:
        writer.disconnect()


def _send_ftp(endpoint: SystemEndpoint, filename: str, payload: str) -> None:
    client = FTP()
    client.connect(endpoint.ftp_host or "", endpoint.ftp_port or 21, timeout=30)
    try:
        client.login(endpoint.ftp_username or "", endpoint.ftp_password or "")
        remote_path = endpoint.ftp_remote_outbox_path or "."
        if remote_path not in {"", ".", "/"}:
            client.cwd(remote_path)
        client.storbinary(f"STOR {filename}", BytesIO(payload.encode("utf-8")))
    finally:
        try:
            client.quit()
        except Exception:
            client.close()


def _fhir_targets(endpoint: SystemEndpoint) -> list[tuple[str, str, Optional[str]]]:
    """Privilégie les configurations FHIR dédiées d'un endpoint."""
    configured = [
        (config.base_url, config.auth_kind or "none", config.auth_token)
        for config in (getattr(endpoint, "fhir_configs", []) or [])
        if isinstance(config, FHIRConfig) and config.is_enabled and config.base_url
    ]
    return configured or ([(endpoint.base_url, endpoint.auth_kind or "none", endpoint.auth_token)] if endpoint.base_url else [])


def enqueue_message(
    session: Session,
    *,
    endpoint_id: int,
    protocol: str,
    payload: str,
    message_type: Optional[str] = None,
    correlation_id: Optional[str] = None,
    source_message_log_id: Optional[int] = None,
    scenario_delivery_id: Optional[int] = None,
    max_attempts: int = 8,
) -> OutboundMessage:
    """Ajoute un message, sans dupliquer une reprise déjà ouverte du même log."""
    if scenario_delivery_id:
        existing = session.exec(
            select(OutboundMessage)
            .where(OutboundMessage.scenario_delivery_id == scenario_delivery_id)
        ).first()
        if existing:
            return existing
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
        scenario_delivery_id=scenario_delivery_id,
        max_attempts=max_attempts,
    )
    session.add(row)
    return row


async def process_outbox_message(session: Session, outbox_id: int) -> OutboundMessage:
    """Traite une ligne précise et conserve une réponse exploitable.

    Ce point d'entrée est utilisé par les jeux de scénario afin de respecter
    leur ordre métier tout en gardant le même mécanisme durable que le worker.
    """
    row = session.get(OutboundMessage, outbox_id)
    if row is None:
        raise ValueError("Message d'outbox introuvable")
    if row.status == "sent":
        return row
    now, ack = datetime.utcnow(), ""
    endpoint = session.get(SystemEndpoint, row.endpoint_id)
    try:
        if not endpoint or not endpoint.is_enabled:
            raise ValueError("Endpoint indisponible ou désactivé")
        protocol = row.protocol.upper()
        if protocol == "MLLP":
            if not endpoint.host or not endpoint.port:
                raise ValueError("Endpoint MLLP incomplet (host/port)")
            ack = await send_mllp(endpoint.host, endpoint.port, row.payload)
            if "MSA|AE|" in ack or "MSA|AR|" in ack:
                raise ValueError(f"ACK négatif: {ack[:300]}")
        elif protocol == "FHIR":
            targets = _fhir_targets(endpoint)
            if not targets:
                raise ValueError("Endpoint FHIR sans base_url")
            payload = json.loads(row.payload)
            status_code, response = 0, {}
            for base_url, auth_kind, auth_token in targets:
                status_code, response = await post_fhir_bundle(base_url, payload, auth_kind, auth_token)
                ack = json.dumps(response or {}, ensure_ascii=False)
                if 200 <= status_code < 300:
                    break
            if not 200 <= status_code < 300:
                raise ValueError(f"FHIR HTTP {status_code}: {ack[:300]}")
        elif protocol == "FILE":
            if not endpoint.outbox_path:
                raise ValueError("Endpoint fichier sans répertoire de sortie")
            folder = Path(endpoint.outbox_path)
            folder.mkdir(parents=True, exist_ok=True)
            suffix = _outbox_suffix(row.message_type)
            file_path = folder / f"outbox_{row.id}{suffix}"
            file_path.write_text(row.payload, encoding="utf-8")
            ack = f"FILE:{file_path.name}"
        elif protocol in {"SFTP", "FTP"}:
            if not endpoint.ftp_host:
                raise ValueError(f"Endpoint {protocol} sans hôte")
            filename = f"outbox_{row.id}{_outbox_suffix(row.message_type)}"
            if protocol == "SFTP":
                await asyncio.to_thread(_send_sftp, endpoint, filename, row.payload)
            else:
                await asyncio.to_thread(_send_ftp, endpoint, filename, row.payload)
            ack = f"{protocol}:{filename}"
        else:
            raise ValueError(f"Protocole d'outbox non supporté: {row.protocol}")
        row.status, row.sent_at, row.last_error, row.response_payload = "sent", now, None, ack
        log = MessageLog(
            direction="out", kind="HPRIM" if protocol == "FILE" and (row.message_type or "").upper().startswith("HPRIM") else protocol,
            endpoint_id=row.endpoint_id, message_type=row.message_type, payload=row.payload,
            ack_payload=ack, status="sent", correlation_id=row.correlation_id,
        )
        session.add(log)
        session.flush()
        if row.source_message_log_id:
            source_log = session.get(MessageLog, row.source_message_log_id)
            if source_log:
                source_log.status, source_log.ack_payload = "sent", ack
                session.add(source_log)
        if row.scenario_delivery_id:
            from app.models_scenario_runs import ScenarioDelivery
            delivery = session.get(ScenarioDelivery, row.scenario_delivery_id)
            if delivery:
                delivery.status, delivery.message_log_id = "sent", log.id
                delivery.ack_code, delivery.response_payload, delivery.error_message = ack[:100], ack, None
                delivery.finished_at, delivery.updated_at = now, now
                session.add(delivery)
    except Exception as exc:  # Evidence is retained even after the final attempt.
        row.attempts += 1
        row.last_error, row.response_payload = str(exc)[:1000], ack or None
        row.status = "failed" if row.attempts >= row.max_attempts else "retry"
        if row.status == "retry":
            row.next_attempt_at = now + timedelta(seconds=min(3600, 2 ** row.attempts))
        if row.scenario_delivery_id:
            from app.models_scenario_runs import ScenarioDelivery
            delivery = session.get(ScenarioDelivery, row.scenario_delivery_id)
            if delivery:
                delivery.status, delivery.error_message = ("error" if row.status == "failed" else "retry"), row.last_error
                delivery.response_payload, delivery.finished_at, delivery.updated_at = row.response_payload, now, now
                session.add(delivery)
    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
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
        processed = await process_outbox_message(session, row.id)
        if processed.status == "sent":
            result["sent"] += 1
        elif processed.status == "failed":
            result["failed"] += 1
        else:
            result["retry"] += 1
    return result
