"""ZBE segment parsing for HL7v2.

This module handles parsing of the ZBE segment (IHE PAM France extension)
which carries movement-specific information.
"""

from datetime import datetime
import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def parse_hl7_datetime(s: Optional[str]) -> Optional[datetime]:
    """Parse HL7 datetime string to Python datetime.
    
    Supports common HL7 formats:
    - YYYYMMDDHHMMSS (full timestamp)
    - YYYYMMDDHHMM (minute precision)
    - YYYYMMDD (date only)
    
    Args:
        s: HL7 datetime string
        
    Returns:
        Parsed datetime or None if invalid
    """
    if not s:
        return None
    s = s.strip()
    
    # Try common HL7 formats
    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(s[: len(fmt.replace("%", ""))], fmt)
        except Exception:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    
    # Fallback: ignore timezone/extra and try first 14 chars
    try:
        return datetime.strptime(s[:14], "%Y%m%d%H%M%S")
    except Exception:
        return None


def parse_zbe(message: str) -> dict:
    """Parse ZBE segment (IHE PAM France compliant extended parsing).

    Extracts:
    - ZBE-1: Movement identifier (principal; TODO: handle repetitions)
    - ZBE-2: Movement date/time (datetime)
    - ZBE-4: Action (INSERT|UPDATE|CANCEL)
    - ZBE-5: Historic flag (Y|N)
    - ZBE-6: Original trigger (required if UPDATE/CANCEL)
    - ZBE-7: UF médicale (XON) -> label (comp1), code (comp10)
    - ZBE-8: UF soins (XON)
    - ZBE-9: Nature code (S,H,M,L,D,SM)
    """
    out = {
        "movement_id": None,
        "movement_datetime": None,
        "action": None,
        "is_historic": False,
        "original_trigger": None,
        "uf_medicale_code": None,
        "uf_medicale_label": None,
        "uf_soins_code": None,
        "uf_soins_label": None,
        "nature": None,
    }

    try:
        lines = re.split(r"\r|\n", message)
        zbe = next((l for l in lines if l.startswith("ZBE")), None)
        if not zbe:
            return out
        parts = zbe.split("|")

        # ZBE-1
        if len(parts) > 1 and parts[1]:
            out["movement_id"] = parts[1]
        # ZBE-2
        if len(parts) > 2 and parts[2]:
            out["movement_datetime"] = parse_hl7_datetime(parts[2])
        # ZBE-4 Action
        if len(parts) > 4 and parts[4]:
            act = parts[4].strip().upper()
            if act in {"INSERT", "UPDATE", "CANCEL"}:
                out["action"] = act
        # ZBE-5 Historic flag
        if len(parts) > 5 and parts[5]:
            out["is_historic"] = parts[5].strip().upper() == "Y"
        # ZBE-6 Original trigger
        if len(parts) > 6 and parts[6]:
            out["original_trigger"] = parts[6].strip().upper()
        # ZBE-7 UF médicale XON
        if len(parts) > 7 and parts[7]:
            comps7 = parts[7].split("^")
            out["uf_medicale_label"] = comps7[0] if len(comps7) > 0 and comps7[0] else None
            if len(comps7) > 9 and comps7[9]:
                out["uf_medicale_code"] = comps7[9]
        # ZBE-8 UF soins XON
        if len(parts) > 8 and parts[8]:
            comps8 = parts[8].split("^")
            out["uf_soins_label"] = comps8[0] if len(comps8) > 0 and comps8[0] else None
            if len(comps8) > 9 and comps8[9]:
                out["uf_soins_code"] = comps8[9]
        # ZBE-9 Nature
        if len(parts) > 9 and parts[9]:
            nature = parts[9].strip().upper()
            if nature in {"S", "H", "M", "L", "D", "SM"}:
                out["nature"] = nature
    except Exception as e:
        logger.error(f"Error parsing ZBE segment: {str(e)}")
    return out
