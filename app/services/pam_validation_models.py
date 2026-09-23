"""Modèles de résultat et diagnostics du validateur IHE PAM."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional
import re

@dataclass
class ValidationIssue:
    """Diagnostic exploitable à la fois par l'API et par les IHM.

    Les trois premiers attributs sont conservés pour compatibilité avec les
    journaux existants. Les suivants permettent à l'IHM de placer précisément
    le curseur sur le segment et le champ à corriger.
    """
    code: str
    message: str
    severity: str = "error"  # error|warn|info
    layer: str = "ihe_pam"  # ihe_pam|structure|hl7_base|datatypes
    location: str = ""
    expected: str = ""
    actual: str = ""


_ISSUE_LOCATION_RE = re.compile(r"^(MSH|EVN|PID|PD1|NK1|PV1|PV2|MRG|ZBE|ZFA|ZFP|ZFV|ZFM|ZFD|ZFS)(?:_?(\d+))?(?:_(\d+))?")


def _issue_layer(code: str) -> str:
    """Classe une issue de façon centralisée, sans heuristique d'IHM."""
    if code.startswith(("MSH", "STRUCTURE")) or code == "EVN_MISMATCH":
        return "hl7_base"
    if any(token in code for token in ("_CX_", "_XPN_", "_XAD_", "_XTN_", "_TS_")) or code.startswith(("PID15", "PV1_2", "PV1_3", "PV1_7")):
        return "datatypes"
    if code.startswith(("SEGMENT", "OPTIONAL_SEGMENTS")) or code.endswith(("_REPEATED", "_ORDER")):
        return "structure"
    return "ihe_pam"


def _issue_location(code: str) -> str:
    """Déduit une localisation HL7 lisible depuis les codes de validation."""
    match = _ISSUE_LOCATION_RE.match(code or "")
    if not match:
        return ""
    segment, field, component = match.groups()
    location = segment
    if field:
        location += f"-{field}"
    if component:
        location += f".{component}"
    return location


def enrich_issues(issues: List[ValidationIssue]) -> List[ValidationIssue]:
    """Complète les diagnostics anciens sans modifier leur sévérité ni texte."""
    for issue in issues:
        if not issue.layer:
            issue.layer = _issue_layer(issue.code)
        elif issue.layer == "ihe_pam":
            issue.layer = _issue_layer(issue.code)
        if not issue.location:
            issue.location = _issue_location(issue.code)
    return issues


@dataclass
class ValidationAuditEntry:
    """Audit trail entry for validation execution."""
    timestamp: str          # ISO 8601 format
    trigger: str            # ADT trigger event
    direction: str          # "in" or "out"
    is_valid: bool
    issues_count: int       # Total issues found
    errors_count: int       # Count of error severity
    warnings_count: int     # Count of warning severity
    profile: str            # Profile used (IHE_PAM_FR)
    strict_semantic: bool   # Semantic strictness flag


@dataclass
class ValidationResult:
    is_valid: bool
    level: str              # ok|warn|fail
    event: str              # e.g., A01
    message_type: str       # e.g., ADT^A01
    issues: List[ValidationIssue]
    audit: Optional[ValidationAuditEntry] = None

    def __post_init__(self) -> None:
        enrich_issues(self.issues)

    def to_dict(self) -> Dict:
        enrich_issues(self.issues)
        return {
            "is_valid": self.is_valid,
            "level": self.level,
            "event": self.event,
            "message_type": self.message_type,
            "issues": [asdict(i) for i in self.issues],
            "audit": asdict(self.audit) if self.audit else None,
        }
