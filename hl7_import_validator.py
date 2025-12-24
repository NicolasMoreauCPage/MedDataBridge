"""
Compatibility shim to expose HL7 import validator at project root.

Some scripts and tests import `from hl7_import_validator import HL7ImportValidator`.
This file re-exports the implementation from scripts.utils.hl7_import_validator.
"""
from scripts.utils.hl7_import_validator import (
    HL7ImportValidator,
    ValidationResult,
    HL7ValidationReport,
)

__all__ = ["HL7ImportValidator", "ValidationResult", "HL7ValidationReport"]
