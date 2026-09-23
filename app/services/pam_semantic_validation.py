"""Validation sémantique des transitions A06/A07."""
from __future__ import annotations

import logging
from typing import List, Optional

from app.services.mllp import parse_msh_fields
from app.services.pam_validation_fields import _get_first_segment
from app.services.pam_validation_models import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

def validate_pam_semantics(
    hl7_message: str,
    venue_id: Optional[int] = None,
    session = None,
    strict: bool = False
) -> ValidationResult:
    """
    Validate semantic coherence of A06/A07 messages with venue movement history.
    
    This is a supplementary validation that checks:
    - A06 (Outpatient→Inpatient): Requires previous movement with nature S
    - A07 (Inpatient→Outpatient): Requires previous movement with nature H
    
    Args:
        hl7_message: HL7 ADT message string
        venue_id: ID of the venue (optional for structural validation)
        session: SQLModel session (required for history check)
        strict: If True, semantic violations are error-level; if False (default), warn-level
    
    Returns:
        ValidationResult: Result with is_valid, level, issues
        - Adds "warn" or "error" level issues based on strict flag
        - If strict=True, semantic problems block validation (is_valid=False)
        - If strict=False (default), allows manual review (is_valid=True + warns)
    
    Note: This validation requires database access (session) and venue context.
    If venue_id or session is None, returns structural validation only.
    """
    issues: List[ValidationIssue] = []
    
    # Parse message to get event code
    msh = parse_msh_fields(hl7_message)
    if not msh:
        return ValidationResult(is_valid=True, level="ok", event="", message_type="", issues=[])
    
    trigger = msh.get("trigger", "")
    if trigger not in ["A06", "A07"]:
        # No semantic validation needed for other codes
        return ValidationResult(is_valid=True, level="ok", event=trigger, message_type="", issues=[])
    
    # If no database context, cannot validate
    if not venue_id or not session:
        issues.append(
            ValidationIssue(
                code="SEMANTIC_CHECK_SKIPPED",
                message=f"{trigger} received but no venue context for semantic validation. "
                        "Skipping history check (set venue_id and session to enable).",
                severity="info"
            )
        )
        return ValidationResult(is_valid=True, level="ok", event=trigger, message_type="", issues=issues)
    
    # Extract nature from ZBE-2 or PV1-2
    pv1_line = _get_first_segment(hl7_message, "PV1")
    zbe_line = _get_first_segment(hl7_message, "ZBE")
    
    current_nature = None
    if zbe_line:
        zbe_parts = zbe_line.split("|")
        if len(zbe_parts) > 2 and zbe_parts[2]:
            current_nature = zbe_parts[2].strip()
    
    if not current_nature and pv1_line:
        pv1_parts = pv1_line.split("|")
        if len(pv1_parts) > 2 and pv1_parts[2]:
            patient_class = pv1_parts[2].strip()
            if patient_class == "I":
                current_nature = "H"
            elif patient_class in ["O", "E"]:
                current_nature = "S"
    
    if not current_nature:
        issues.append(
            ValidationIssue(
                code="SEMANTIC_NATURE_UNKNOWN",
                message=f"{trigger} received but current nature (S/H) not found in message. "
                        "Cannot validate transition.",
                severity="warn"
            )
        )
        return ValidationResult(is_valid=True, level="warn", event=trigger, message_type="", issues=issues)
    
    # Query previous movements on venue
    try:
        from sqlmodel import select
        from app.models import Mouvement
        
        # Get movement timestamp
        evn_line = _get_first_segment(hl7_message, "EVN")
        when_str = None
        if evn_line:
            evn_parts = evn_line.split("|")
            if len(evn_parts) > 2:
                when_str = evn_parts[2]
        
        from datetime import datetime
        when_dt = None
        if when_str:
            try:
                when_dt = datetime.strptime(when_str[:14], "%Y%m%d%H%M%S")
            except Exception as exc:
                logger.debug("Optional operation skipped", exc_info=exc)
        # Query previous movements
        previous_movements = session.exec(
            select(Mouvement)
            .where(Mouvement.venue_id == venue_id)
            .where(Mouvement.when < when_dt if when_dt else True)
            .order_by(Mouvement.when.desc())
        ).all()
        
        if not previous_movements:
            issues.append(
                ValidationIssue(
                    code="SEMANTIC_NO_HISTORY",
                    message=f"{trigger} received but no previous movements on venue {venue_id}. "
                            "Cannot validate {S→H or H→S} transition.",
                    severity="warn"
                )
            )
            return ValidationResult(is_valid=True, level="warn", event=trigger, message_type="", issues=issues)
        
        # Find last movement with defined nature
        last_nature = None
        for prev in previous_movements:
            if hasattr(prev, "nature") and getattr(prev, "nature") in ["H", "S", "O"]:
                last_nature = getattr(prev, "nature")
                break
        
        if not last_nature:
            issues.append(
                ValidationIssue(
                    code="SEMANTIC_NO_PREVIOUS_NATURE",
                    message=f"{trigger} received but no previous movement with defined nature. "
                            "Cannot validate transition.",
                    severity="warn"
                )
            )
            return ValidationResult(is_valid=True, level="warn", event=trigger, message_type="", issues=issues)
        
        # Validate A06: S → H
        if trigger == "A06":
            if last_nature != "S":
                issues.append(
                    ValidationIssue(
                        code="SEMANTIC_A06_INVALID_TRANSITION",
                        message=f"A06 (Outpatient→Inpatient) received but last nature is '{last_nature}' not 'S'. "
                                f"Coherence issue detected.",
                        severity="warn"
                    )
                )
            if current_nature != "H":
                issues.append(
                    ValidationIssue(
                        code="SEMANTIC_A06_INVALID_CURRENT",
                        message=f"A06 received but current nature is '{current_nature}' not 'H'. "
                                f"Incoherent message.",
                        severity="warn"
                    )
                )
        
        # Validate A07: H → S
        elif trigger == "A07":
            if last_nature != "H":
                issues.append(
                    ValidationIssue(
                        code="SEMANTIC_A07_INVALID_TRANSITION",
                        message=f"A07 (Inpatient→Outpatient) received but last nature is '{last_nature}' not 'H'. "
                                f"Coherence issue detected.",
                        severity="warn"
                    )
                )
            if current_nature != "S":
                issues.append(
                    ValidationIssue(
                        code="SEMANTIC_A07_INVALID_CURRENT",
                        message=f"A07 received but current nature is '{current_nature}' not 'S'. "
                                f"Incoherent message.",
                        severity="warn"
                    )
                )
    
    except Exception as e:
        issues.append(
            ValidationIssue(
                code="SEMANTIC_CHECK_ERROR",
                message=f"Semantic validation error: {str(e)}",
                severity="warn"
            )
        )
    
    # Determine level (considering strict flag)
    has_error = any(i.severity == "error" for i in issues)
    has_warn = any(i.severity == "warn" for i in issues)
    
    # If strict mode, treat warnings as errors for semantic checks
    if strict and has_warn:
        for issue in issues:
            if issue.severity == "warn":
                issue.severity = "error"
        has_error = True
    
    level = "fail" if has_error else ("warn" if has_warn else "ok")
    is_valid = not has_error  # Valid only if no errors (considering strict mode)
    
    return ValidationResult(is_valid=is_valid, level=level, event=trigger, message_type="", issues=issues)
