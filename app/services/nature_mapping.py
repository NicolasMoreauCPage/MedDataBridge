"""Mapping helper for deriving ZBE-9 nature codes from trigger events / movement context.

Centralizes logic so generator and inbound processing stay consistent.
"""
from __future__ import annotations
from typing import Optional

# Canonical set of valid nature codes per spec (S,H,M,L,D,SM)
VALID_NATURES = {"S", "H", "M", "L", "D", "SM"}

# Basic trigger->nature defaults (can be extended)
TRIGGER_DEFAULTS = {
    "A01": "H",  # Admission / Hospitalisation
    "A04": "H",  # Inscription (treated like hospital context start)
    "A05": "H",  # Pre-admission
    "A02": "M",  # Mutation / Transfer
    "A03": "S",  # Sortie / Discharge
    "A11": "H",  # Cancel admission (still nature admission)
    "A12": "M",  # Cancel transfer
    "A13": "S",  # Cancel discharge
}

def derive_nature(trigger: Optional[str], existing: Optional[str] = None) -> Optional[str]:
    """Derive nature code.

    Priority:
    1. existing if valid (already set on movement)
    2. mapping from trigger
    3. None (caller may leave blank)
    """
    if existing and existing in VALID_NATURES:
        return existing
    if trigger and trigger in TRIGGER_DEFAULTS:
        return TRIGGER_DEFAULTS[trigger]
    return existing if existing in VALID_NATURES else None
