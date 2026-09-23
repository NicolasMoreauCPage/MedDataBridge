"""Emission historique vers les endpoints FILE et SFTP.

Ce module garde les détails de transport et de journalisation hors de
``emit_on_create``. Les générateurs sont injectés afin de préserver les points
de monkeypatch existants et d'éviter une dépendance circulaire.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Callable

from sqlmodel import Session

from app.models_endpoints import MessageLog
from app.utils.atomic_write import write_atomic_text_file

logger = logging.getLogger(__name__)

PAM_ENTITY_TYPES = {"patient", "venue", "mouvement"}


def _payload_for(
    entity,
    entity_type: str,
    session: Session,
    endpoint,
    operation: str,
    generate_pam: Callable,
    generate_fhir: Callable,
) -> tuple[str, str]:
    hl7_payload = None
    if entity_type in PAM_ENTITY_TYPES:
        hl7_payload = generate_pam(
            entity,
            entity_type,
            session,
            operation=operation,
            msh_sending_app=getattr(endpoint, "sending_app", None),
            msh_sending_facility=getattr(endpoint, "sending_facility", None),
            msh_receiving_app=getattr(endpoint, "receiving_app", None),
            msh_receiving_facility=getattr(endpoint, "receiving_facility", None),
        )
    if hl7_payload:
        return hl7_payload, "hl7"
    return json.dumps(generate_fhir(entity, entity_type, session), default=str), "json"


def _filename(entity, entity_type: str, extension: str) -> str:
    suffix = f"{int(time.time())}-{random.randint(1000, 9999)}"
    return f"{entity_type}_{getattr(entity, 'id', 'unknown')}_{suffix}.{extension}"


def _record(
    session: Session,
    *,
    endpoint_id: int | None,
    kind: str,
    payload: str,
    acknowledgement: str,
    status: str,
    correlation_id: str | None,
) -> None:
    session.add(MessageLog(
        direction="out",
        kind=kind,
        endpoint_id=endpoint_id,
        payload=payload[:100000] if payload else "",
        ack_payload=acknowledgement,
        status=status,
        correlation_id=correlation_id,
    ))
    session.commit()


def _write_file(endpoint, filename: str, payload: str, extension: str) -> str:
    base = Path(getattr(endpoint, "outbox_path", None) or os.environ.get("MEDBRIDGE_OUT_DIR") or "/tmp/medbridge_generated")
    subdirectory = "pam" if extension == "hl7" else "fhir" if extension == "json" else extension
    path = write_atomic_text_file(base / subdirectory / filename, payload)
    return f"WROTE:{path}"


def _write_sftp(endpoint, filename: str, payload: str) -> str:
    from app.adapters.sftp_writer import SFTPWriter

    writer = SFTPWriter(
        host=endpoint.ftp_host,
        port=endpoint.ftp_port or 22,
        username=endpoint.ftp_username,
        password=endpoint.ftp_password,
        remote_path=endpoint.ftp_remote_outbox_path or ".",
    )
    writer.connect()
    try:
        writer.write_file(filename, payload)
    finally:
        writer.disconnect()
    return f"SENT_SFTP:{filename}"


def emit_file_endpoint(
    session: Session,
    *,
    endpoint,
    entity,
    entity_type: str,
    operation: str,
    generate_pam: Callable,
    generate_fhir: Callable,
) -> None:
    """Génère, transporte et journalise une livraison FILE ou SFTP."""
    kind = str(endpoint.kind).upper()
    endpoint_id = getattr(endpoint, "id", None)
    correlation_id = getattr(entity, "correlation_id", None)
    payload = ""
    try:
        payload, extension = _payload_for(
            entity, entity_type, session, endpoint, operation, generate_pam, generate_fhir
        )
        filename = _filename(entity, entity_type, extension)
        acknowledgement = (
            _write_sftp(endpoint, filename, payload)
            if kind == "SFTP"
            else _write_file(endpoint, filename, payload, extension)
        )
        _record(
            session,
            endpoint_id=endpoint_id,
            kind=kind,
            payload=payload,
            acknowledgement=acknowledgement,
            status="sent",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.exception("Échec de livraison %s pour endpoint=%s", kind, endpoint_id)
        session.rollback()
        try:
            _record(
                session,
                endpoint_id=endpoint_id if isinstance(endpoint_id, int) else None,
                kind=kind,
                payload=payload,
                acknowledgement=str(exc),
                status="error",
                correlation_id=correlation_id,
            )
        except Exception:
            logger.exception("Impossible de journaliser l'échec %s", kind)
