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
    """Parse ZBE segment (IHE PAM France extension).
    
    The ZBE segment carries movement-specific information:
    - ZBE-1: Movement identifier
    - ZBE-2: Movement date/time
    - ZBE-6: Original trigger event (for Z99 updates)
    - ZBE-9: Movement indicator (N=new movement, C=correction)
    
    Args:
        message: Complete HL7v2 message
        
    Returns:
        Dictionary with keys: movement_id, movement_datetime, 
        original_trigger, movement_indicator
    """
    out = {
        "movement_id": None,
        "movement_datetime": None,
        "original_trigger": None,
        "movement_indicator": None,
    }
    
    try:
        lines = re.split(r"\r|\n", message)
        zbe = next((l for l in lines if l.startswith("ZBE")), None)
        if not zbe:
            return out
        
        parts = zbe.split("|")
        
        # ZBE-1: Movement identifier
        if len(parts) > 1 and parts[1]:
            out["movement_id"] = parts[1]
        
        # ZBE-2: Movement date/time
        if len(parts) > 2 and parts[2]:
            out["movement_datetime"] = parse_hl7_datetime(parts[2])
        
        # ZBE-6: Original trigger event (for Z99 partial updates)
        if len(parts) > 6 and parts[6]:
            out["original_trigger"] = parts[6]
        
        # ZBE-9: Movement indicator / Processing mode
        if len(parts) > 9 and parts[9]:
            out["movement_indicator"] = parts[9].strip().upper()
            
    except Exception as e:
        logger.error(f"Error parsing ZBE segment: {str(e)}")
    
    return out
