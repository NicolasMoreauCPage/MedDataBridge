"""Primitives partagées de construction des messages PAM sortants."""

import logging
import time
from typing import Optional, Sequence

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlmodel import Session

logger = logging.getLogger(__name__)


def safe_query(session: Session, statement, max_retries: int = 3):
    """Exécute une lecture SQLite tolérante aux verrous transitoires."""
    for attempt in range(max_retries):
        try:
            return session.exec(statement).first()
        except (InterfaceError, OperationalError) as error:
            if "out of sequence" in str(error) or "database is locked" in str(error):
                if attempt < max_retries - 1:
                    time.sleep(0.05 * (attempt + 1))
                    session.rollback()
                    continue
            logger.warning("Erreur SQLite à la tentative %s/%s : %s", attempt + 1, max_retries, error)
            if attempt == max_retries - 1:
                return None
    return None


def clean_hl7_value(value: object) -> str:
    """Convertit les valeurs vides ou textuellement ``None`` en champ HL7 vide."""
    if value is None:
        return ""
    if isinstance(value, str):
        normalized = value.strip()
        return "" if normalized.lower() == "none" else normalized
    return str(value)


def normalize_mrg_prior_identifiers(identifiers: Optional[Sequence[object]]) -> list[str]:
    """Normalise les répétitions CX de MRG-1 et refuse les séparateurs HL7."""
    normalized = [
        repetition.strip()
        for value in identifiers or []
        for repetition in str(value or "").split("~")
        if repetition.strip()
    ]
    if any("|" in value or "\r" in value or "\n" in value for value in normalized):
        raise ValueError("MRG-1 doit contenir des identifiants CX sans séparateur de segment ou de champ")
    return normalized


def new_message_control_id(seed: object) -> str:
    """Construit un MSH-10 unique, indépendant des identifiants métier."""
    from uuid import uuid4

    return f"{seed}-{uuid4().hex[:12]}"
