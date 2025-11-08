"""Segment presence checker for HL7v2 messages."""

import re


def has_segment(message: str, segment_name: str) -> bool:
    """Check if a segment is present in the message.
    
    Args:
        message: Complete HL7v2 message
        segment_name: Three-letter segment identifier (e.g., "PID", "ZBE")
        
    Returns:
        True if segment is present, False otherwise
    """
    lines = re.split(r"\r|\n", message)
    return any(l.startswith(segment_name) for l in lines)
