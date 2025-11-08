"""Transition validation for IHE PAM workflow.

This module provides validation of ADT event sequences according to IHE PAM
profiles, with support for relaxed validation mode.
"""

import logging
import os
from typing import Optional

from app.state_transitions import assert_transition

logger = logging.getLogger(__name__)


def validate_transition(
    previous_event: Optional[str],
    incoming_trigger: str,
    identity_only_triggers: Optional[set] = None,
    relax: Optional[bool] = None,
) -> tuple[bool, Optional[str]]:
    """Validate IHE PAM transition from previous event to incoming trigger.
    
    Args:
        previous_event: Previous ADT trigger code (or None for initial)
        incoming_trigger: Incoming ADT trigger code
        identity_only_triggers: Set of triggers exempt from validation (A28, A31, A40, A47)
        relax: Override for relaxed mode (if None, reads PAM_RELAX_TRANSITIONS env var)
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if transition is valid
        - (False, error_text) if transition is invalid
    """
    # Default identity-only triggers (identity management, no venue workflow)
    if identity_only_triggers is None:
        identity_only_triggers = {"A28", "A31", "A40", "A47"}
    
    # Check relaxed mode
    if relax is None:
        relax = os.getenv("PAM_RELAX_TRANSITIONS", "0") in ("1", "true", "True")
    
    # Skip validation for identity-only triggers
    if incoming_trigger in identity_only_triggers:
        return (True, None)
    
    # Skip validation if relaxed mode
    if relax:
        logger.info(
            "[RELAX] Transition validation skipped",
            extra={"trigger": incoming_trigger, "previous_event": previous_event}
        )
        return (True, None)
    
    # Validate transition
    try:
        assert_transition(previous_event, incoming_trigger)
        return (True, None)
    except ValueError as ve:
        error_text = str(ve)
        logger.warning(
            "Transition IHE PAM invalide",
            extra={
                "trigger": incoming_trigger,
                "previous_event": previous_event,
                "error": error_text
            }
        )
        return (False, error_text)
