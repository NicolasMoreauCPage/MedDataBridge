"""Responsabilités d'émission PAM extraites de l'orchestrateur historique."""

from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

logger = logging.getLogger(__name__)


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
