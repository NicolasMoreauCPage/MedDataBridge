"""PV1 segment parsing for HL7v2.

This module handles parsing of Patient Visit (PV1) segments,
extracting location, patient class, admit/discharge times, and visit identifiers.
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


def parse_pv1(message: str) -> dict:
    """Parse PV1 segment to extract visit information.
    
    Extracts:
    - PV1-2: Patient class (I=inpatient, O=outpatient, E=emergency, etc.)
    - PV1-3: Assigned patient location (point of care^room^bed^facility)
    - PV1-6: Prior patient location
    - PV1-10: Hospital service
    - PV1-19: Visit number / Visit ID (often CX format)
    - PV1-44: Admit date/time
    - PV1-45: Discharge date/time
    
    Args:
        message: Complete HL7v2 message
        
    Returns:
        Dictionary with parsed PV1 fields
    """
    out = {
        "location": "",
        "previous_location": "",
        "hospital_service": "",
        "admit_time": None,
        "discharge_time": None,
        "patient_class": "",
        "visit_number": None,
    }
    
    try:
        lines = re.split(r"\r|\n", message)
        pv1 = next((l for l in lines if l.startswith("PV1")), None)
        if not pv1:
            return out
        
        parts = pv1.split("|")
        
        # PV1-2: Patient class
        if len(parts) > 2 and parts[2]:
            out["patient_class"] = parts[2]
        
        # PV1-3: Assigned patient location
        if len(parts) > 3 and parts[3]:
            out["location"] = parts[3]
        
        # PV1-6: Prior patient location
        if len(parts) > 6 and parts[6]:
            out["previous_location"] = parts[6]
        
        # PV1-10: Hospital service
        if len(parts) > 10 and parts[10]:
            out["hospital_service"] = parts[10]
        
        # PV1-19: Visit Number / Visit ID (often CX format)
        if len(parts) > 19 and parts[19]:
            out["visit_number"] = parts[19]
        
        # PV1-44: Admit date/time
        if len(parts) > 44 and parts[44]:
            out["admit_time"] = parse_hl7_datetime(parts[44])
        
        # PV1-45: Discharge date/time
        if len(parts) > 45 and parts[45]:
            out["discharge_time"] = parse_hl7_datetime(parts[45])
            
    except Exception as e:
        logger.error(f"Error parsing PV1 segment: {str(e)}")
    
    return out
