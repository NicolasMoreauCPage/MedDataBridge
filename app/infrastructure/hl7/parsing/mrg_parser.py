"""MRG segment parsing for HL7v2.

This module handles parsing of the MRG (Merge Patient Information) segment
used in A40 (merge patients) and A47 (change patient identifier) messages.
"""

import re
import logging

logger = logging.getLogger(__name__)


def parse_mrg(message: str) -> dict:
    """Parse MRG segment for patient merge operations.
    
    The MRG segment contains information about the prior patient identifier:
    - MRG-1: Prior Patient Identifier List (CX format)
    - MRG-7: Prior Patient Name (XPN format)
    
    Used in:
    - A40: Merge patients
    - A47: Change patient identifier
    
    Args:
        message: Complete HL7v2 message
        
    Returns:
        Dictionary with keys: prior_patient_id, prior_patient_name
    """
    out = {
        "prior_patient_id": None,
        "prior_patient_name": None,
    }
    
    try:
        lines = re.split(r"\r|\n", message)
        mrg = next((l for l in lines if l.startswith("MRG")), None)
        if not mrg:
            return out
        
        parts = mrg.split("|")
        
        # MRG-1: Prior Patient Identifier List
        if len(parts) > 1 and parts[1]:
            out["prior_patient_id"] = parts[1]
        
        # MRG-7: Prior Patient Name
        if len(parts) > 7 and parts[7]:
            out["prior_patient_name"] = parts[7]
            
    except Exception as e:
        logger.error(f"Error parsing MRG segment: {str(e)}")
    
    return out
