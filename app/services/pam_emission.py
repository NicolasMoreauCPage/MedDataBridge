"""Responsabilités d'émission PAM extraites de l'orchestrateur historique."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlmodel import Session, select

from app.models_endpoints import MessageLog
from app.services.outbox_service import enqueue_message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PamValidationOutcome:
    """Résultat sérialisable de la validation d'un PAM sortant."""

    status: str
    issues: str
    first_error: str | None = None


def validate_outbound_pam(
    payload: str,
    *,
    validator: Callable[..., object] | None = None,
) -> PamValidationOutcome:
    """Valide un payload sortant sans laisser une erreur interne bloquer l'émission."""
    if validator is None:
        from app.services.pam_validation import validate_pam

        validator = validate_pam
    try:
        result = validator(payload, direction="out")
        issues = list(getattr(result, "issues", []))
        first_error = next(
            (getattr(issue, "message", None) for issue in issues if getattr(issue, "severity", None) == "error"),
            None,
        )
        return PamValidationOutcome(
            status=getattr(result, "level", "warn"),
            issues=json.dumps(
                [getattr(issue, "__dict__", {}) for issue in issues],
                ensure_ascii=False,
            ),
            first_error=first_error,
        )
    except Exception:
        return PamValidationOutcome(
            status="warn",
            issues=json.dumps(
                [{"code": "VALIDATOR_ERROR", "message": "Erreur interne du validateur", "severity": "warn"}],
                ensure_ascii=False,
            ),
        )


def _resolve_transport_result(result: object) -> object:
    """Résout un transport asynchrone, y compris depuis une boucle active."""
    if not inspect.iscoroutine(result):
        return result
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(result)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, result)
        return future.result(timeout=12)


def send_outbound_pam(
    host: str,
    port: int,
    payload: str,
    *,
    message_type: str = "ADT^unknown",
    sender: Callable[[str, int, str], object] | None = None,
) -> tuple[str, str]:
    """Envoie un PAM sur MLLP et traduit son ACK en statut de livraison."""
    started_at = time.time()
    ack_code = ""
    try:
        if sender is None:
            # Import tardif : les tests remplacent le transport sur son module.
            from app.services.mllp import send_mllp

            sender = send_mllp
        acknowledgment = _resolve_transport_result(sender(host, port, payload))
        acknowledgment = str(acknowledgment or "")
        msa_line = next(
            (line for line in acknowledgment.split("\r") if line.startswith("MSA|")),
            None,
        )
        if not msa_line:
            return "error", "[ACK MLLP sans segment MSA]"
        parts = msa_line.split("|")
        ack_code = parts[1] if len(parts) > 1 else ""
        return ("error" if ack_code in {"AE", "AR"} else "sent"), acknowledgment
    except Exception as exc:
        return "error", str(exc)
    finally:
        try:
            from app.metrics import record_pam_ack

            record_pam_ack(
                direction="outbound",
                ack_code=ack_code,
                message_type=message_type,
                duration_seconds=time.time() - started_at,
            )
        except Exception:
            logger.debug("Impossible d'enregistrer la métrique ACK PAM", exc_info=True)


def dump_outbound_pam_payload(payload: str | None, entity_id: object) -> None:
    """Conserve un payload MLLP émis pour diagnostic, sans bloquer l'émission."""
    if not payload or payload.startswith("[Emission error"):
        return
    try:
        output_dir = Path(os.environ.get("MEDBRIDGE_OUT_DIR") or "/tmp/medbridge_generated") / "pam"
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{int(time.time())}-{random.randint(1000, 9999)}"
        destination = output_dir / f"mllp_{entity_id}_{suffix}.hl7"
        temporary = destination.with_suffix(".hl7.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(destination)
    except Exception:
        logger.exception("Failed to dump outbound MLLP HL7")


def upsert_outbound_pam_log(
    session: Session,
    *,
    endpoint_id: int,
    correlation_id: str | None,
    payload: str | None,
    acknowledgment: str | None,
    status: str,
    validation_status: str,
    validation_issues: str,
) -> MessageLog:
    """Enregistre un unique journal PAM par corrélation ou échec en attente."""
    if correlation_id:
        existing = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint_id)
            .where(MessageLog.direction == "out")
            .where(MessageLog.correlation_id == correlation_id)
        ).first()
    else:
        existing = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint_id)
            .where(MessageLog.kind == "MLLP")
            .where(MessageLog.status.in_(["error", "pending"]))
            .order_by(MessageLog.created_at.desc())
        ).first()

    if existing:
        existing.payload = payload or ""
        existing.ack_payload = acknowledgment or ""
        existing.status = status
        existing.pam_validation_status = validation_status
        existing.pam_validation_issues = validation_issues
        existing.created_at = datetime.utcnow()
        log = existing
    else:
        log = MessageLog(
            direction="out", kind="MLLP", endpoint_id=endpoint_id,
            payload=payload or "", ack_payload=acknowledgment or "", status=status,
            pam_validation_status=validation_status,
            pam_validation_issues=validation_issues, correlation_id=correlation_id,
        )
        session.add(log)
    session.commit()
    return log


def emit_outbound_pam_attempt(
    session: Session,
    *,
    endpoint: object,
    payload: str | None,
    correlation_id: str | None,
    entity_id: object,
    message_type: str = "ADT^unknown",
) -> tuple[MessageLog, str]:
    """Exécute une tentative PAM et délègue les reprises réseau à l'outbox."""
    payload = payload or "[Emission error: HL7 message missing]"
    validation = validate_outbound_pam(payload)
    status = "generated"
    acknowledgment = ""
    if validation.status == "fail":
        status = "validation_failed"
        first_error = validation.first_error or "Message PAM sortant non conforme"
        acknowledgment = f"[Emission bloquée : {first_error}]"
    else:
        status, acknowledgment = send_outbound_pam(
            getattr(endpoint, "host"),
            getattr(endpoint, "port"),
            payload,
            message_type=message_type,
        )

    message_log = upsert_outbound_pam_log(
        session,
        endpoint_id=getattr(endpoint, "id"),
        correlation_id=correlation_id,
        payload=payload,
        acknowledgment=acknowledgment,
        status=status,
        validation_status=validation.status,
        validation_issues=validation.issues,
    )
    dump_outbound_pam_payload(payload, entity_id)
    if status == "error":
        enqueue_message(
            session,
            endpoint_id=getattr(endpoint, "id"),
            protocol="MLLP",
            payload=payload,
            message_type="HL7",
            correlation_id=correlation_id,
            source_message_log_id=message_log.id,
        )
        session.commit()
    return message_log, status
