"""Minimal stub for hl7_import_validator used in tests.

This stub provides lightweight classes and functions expected by tests
so test collection can proceed in environments where the real
hl7_import_validator package is not installed.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class ValidationResult:
    valid: bool = True
    errors: List[str] = None


class HL7ImportValidator:
    def __init__(self, *args, **kwargs):
        pass

    def validate(self, payload):
        return ValidationResult(valid=True, errors=[])


class HL7ImportQualityReport:
    def __init__(self, *args, **kwargs):
        pass

    def summary(self):
        return {}
