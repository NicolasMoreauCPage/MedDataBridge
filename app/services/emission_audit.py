"""Traçabilité des émissions générées sans cible configurée."""

import json
import logging
import os
from pathlib import Path
from typing import Callable

from sqlmodel import Session

from app.models.endpoints import MessageLog
from app.services.pam_emission import validate_outbound_pam

logger = logging.getLogger(__name__)


def persist_generated_payloads(
    session: Session,
    entity,
    entity_type: str,
    generate_pam: Callable,
    generate_fhir: Callable,
) -> None:
    """Conserve les payloads générés quand aucun endpoint émetteur n'existe."""
    hl7_payload = generate_pam(entity, entity_type, session)
    validation = validate_outbound_pam(hl7_payload)
    fhir_payload = generate_fhir(entity, entity_type, session)
    session.add(MessageLog(
        direction="out", kind="MLLP", endpoint_id=None, payload=hl7_payload or "", ack_payload="",
        status="generated", pam_validation_status=validation.status, pam_validation_issues=validation.issues,
    ))
    session.add(MessageLog(
        direction="out", kind="FHIR", endpoint_id=None,
        payload=json.dumps(fhir_payload, default=str) if fhir_payload is not None else "", ack_payload="", status="generated",
    ))
    session.commit()
    _write_preview_files(entity, entity_type, hl7_payload, fhir_payload)


def _write_preview_files(entity, entity_type: str, hl7_payload: str | None, fhir_payload) -> None:
    """Écrit une prévisualisation locale facultative, sans faire échouer l'émission."""
    try:
        from app.utils.atomic_write import write_atomic_text

        base = Path(os.environ.get("MEDBRIDGE_OUT_DIR") or "/tmp/medbridge_generated")
        entity_id = getattr(entity, "id", "unknown")
        if hl7_payload:
            write_atomic_text(base / "pam", f"{entity_type}_{entity_id}", hl7_payload, extension=".hl7")
        if fhir_payload is not None:
            write_atomic_text(
                base / "fhir", f"fhir_{entity_type}_{entity_id}",
                json.dumps(fhir_payload, default=str, ensure_ascii=False), extension=".json",
            )
    except Exception:
        logger.exception("Impossible d'écrire les prévisualisations d'émission")
