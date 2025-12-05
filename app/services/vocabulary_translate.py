"""Utilities for translating codes between vocabulary systems using VocabularyMapping.

Inbound (HL7 -> internal/FHIR):
    map_code(session, "patient-class", "I", "encounter-class") -> "IMP"

Outbound (internal/FHIR -> HL7):
    reverse_map_code(session, "encounter-class", "IMP", "patient-class") -> "I"

The mapping table stores rows in one direction only (source_value -> target_system).
For reverse lookup we search mappings whose target_system matches and target_code equals
the desired code, then return the source value code.
"""
from __future__ import annotations
from typing import Optional
from sqlmodel import Session, select
from app.models_vocabulary import VocabularySystem, VocabularyValue, VocabularyMapping
from app.services.vocabulary_fallback import get_default_value


def map_code(
    session: Session,
    source_system_name: str,
    source_code: str,
    target_system_name: str,
) -> Optional[str]:
    """Map a code from one system to another via VocabularyMapping.

    Args:
        session: DB session
        source_system_name: system name of the source code
        source_code: code in the source system to translate
        target_system_name: target system name

    Returns:
        Mapped target code or None if no mapping found.
    """
    if not source_code:
        return None

    source_system = session.exec(
        select(VocabularySystem).where(VocabularySystem.name == source_system_name)
    ).first()
    target_system = session.exec(
        select(VocabularySystem).where(VocabularySystem.name == target_system_name)
    ).first()
    if not source_system or not target_system:
        return None

    value = session.exec(
        select(VocabularyValue)
        .where(VocabularyValue.system_id == source_system.id)
        .where(VocabularyValue.code == source_code)
    ).first()
    if not value:
        return None

    mapping = session.exec(
        select(VocabularyMapping)
        .where(VocabularyMapping.source_value_id == value.id)
        .where(VocabularyMapping.target_system_id == target_system.id)
    ).first()
    if not mapping:
        return None
    return mapping.target_code


def reverse_map_code(
    session: Session,
    target_system_name: str,
    target_code: str,
    source_system_name: str,
) -> Optional[str]:
    """Reverse mapping: obtain source system code from a target system code.

    Since VocabularyMapping rows are stored source->target only, we search for a
    mapping whose target system & code match then return the source value code.
    """
    if not target_code:
        return None

    target_system = session.exec(
        select(VocabularySystem).where(VocabularySystem.name == target_system_name)
    ).first()
    source_system = session.exec(
        select(VocabularySystem).where(VocabularySystem.name == source_system_name)
    ).first()
    if not target_system or not source_system:
        return None

    mapping = session.exec(
        select(VocabularyMapping)
        .where(VocabularyMapping.target_system_id == target_system.id)
        .where(VocabularyMapping.target_code == target_code)
    ).first()
    if not mapping:
        return None

    # Ensure the source value indeed belongs to the requested source system
    if mapping.source_value.system_id != source_system.id:
        return None
    return mapping.source_value.code


def safe_map(
    session: Session,
    source_system: str,
    code: Optional[str],
    target_system: str,
    *,
    fallback_same: bool = True,
) -> Optional[str]:
    """Helper: try mapping; optionally fallback to same code if not found."""
    if not code:
        return None
    mapped = map_code(session, source_system, code, target_system)
    if mapped:
        return mapped
    return code if fallback_same else None


def map_code_with_fallback(
    session: Session,
    source_system: str,
    source_code: str,
    target_system: str,
    fallback_to_default: bool = True
) -> Optional[str]:
    """
    Map a code with fallback to default values if mapping not found.

    Args:
        session: DB session
        source_system: system name of the source code
        source_code: code in the source system to translate
        target_system: target system name
        fallback_to_default: if True, use default values when no mapping found

    Returns:
        Mapped target code, default value, or None if no mapping and no default
    """
    if not source_code:
        return None

    # Essayer d'abord le mapping normal
    mapped = map_code(session, source_system, source_code, target_system)
    if mapped:
        return mapped

    # Si pas de mapping et Solution de repli activé, essayer les valeurs par défaut
    if fallback_to_default:
        default_value = get_default_value(target_system, source_code)
        if default_value:
            return default_value

    return None
