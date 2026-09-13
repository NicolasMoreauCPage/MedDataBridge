"""Validation des payloads finaux avant création de l'outbox.

Le validateur travaille sur le message compilé, après remplacement des
identifiants, dates, UF et professionnels. C'est cet artefact précis qui sera
émis et qui doit donc porter la preuve de validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any
from xml.etree import ElementTree as ET

from app.services.fhir_profile_validator import FHIRProfileValidator
from app.services.hprim.hprim_validator import HprimValidator
from app.services.pam_validation import validate_pam
from app.services.siu import validate_siu
from app.validators.hl7_validators import MFNValidator


@dataclass(frozen=True)
class OutputValidationReport:
    valid: bool
    validator: str
    errors: list[str]
    warnings: list[str]

    @property
    def status(self) -> str:
        return "invalid" if not self.valid else "warning" if self.warnings else "valid"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "status": self.status}


def _issue_text(issue: Any) -> str:
    code = getattr(issue, "code", None)
    message = getattr(issue, "message", str(issue))
    return f"{code}: {message}" if code else message


def _hl7_report(payload: str) -> OutputValidationReport:
    msh = next((line for line in payload.replace("\n", "\r").split("\r") if line.startswith("MSH|")), "")
    if not msh:
        return OutputValidationReport(False, "HL7 v2", ["Le message doit commencer par MSH"], [])
    fields = msh.split("|")
    message_type = fields[8].upper() if len(fields) > 8 else ""
    if message_type.startswith("ADT^"):
        result = validate_pam(payload, direction="out")
        errors = [_issue_text(item) for item in result.issues if item.severity == "error"]
        warnings = [_issue_text(item) for item in result.issues if item.severity != "error"]
        return OutputValidationReport(not errors, "IHE PAM France", errors, warnings)
    if message_type.startswith("SIU^"):
        result = validate_siu(payload, direction="out")
        errors = [_issue_text(item) for item in result.issues if item.severity == "error"]
        warnings = [_issue_text(item) for item in result.issues if item.severity != "error"]
        return OutputValidationReport(not errors, "HL7 SIU", errors, warnings)
    if message_type.startswith("MFN^"):
        result = MFNValidator().validate_message(payload)
        return OutputValidationReport(
            result.is_valid,
            "HL7 MFN",
            [_issue_text(item) for item in result.errors],
            [_issue_text(item) for item in result.warnings],
        )
    required = {
        "MSH-9": message_type,
        "MSH-10": fields[9] if len(fields) > 9 else "",
        "MSH-12": fields[11] if len(fields) > 11 else "",
    }
    errors = [f"{name} est requis" for name, value in required.items() if not value]
    return OutputValidationReport(not errors, "HL7 v2", errors, [])


def _xml_report(payload: str) -> OutputValidationReport:
    try:
        ET.fromstring(payload)
    except ET.ParseError as exc:
        return OutputValidationReport(False, "XML", [f"XML invalide: {exc}"], [])
    validator = HprimValidator()
    schema = validator.guess_schema_name(payload)
    if not schema:
        return OutputValidationReport(True, "XML", [], ["Racine HPRIM non reconnue : validation XML seule"])
    valid, errors = validator.validate_xml_string(payload, schema)
    return OutputValidationReport(valid, f"HPRIM XSD ({schema})", errors, [])


def _fhir_report(payload: str) -> OutputValidationReport:
    try:
        resource = json.loads(payload)
    except json.JSONDecodeError as exc:
        return OutputValidationReport(False, "FHIR R4", [f"JSON invalide: {exc.msg}"], [])
    if not isinstance(resource, dict) or not resource.get("resourceType"):
        return OutputValidationReport(False, "FHIR R4", ["resourceType est requis"], [])
    bundle = resource if resource.get("resourceType") == "Bundle" else {
        "resourceType": "Bundle", "type": "collection", "entry": [{"resource": resource}],
    }
    result = FHIRProfileValidator().validate_bundle(bundle, strict=True, profile="fr-core")
    return OutputValidationReport(result.valid, "FHIR R4 / FR Core", result.errors, result.warnings)


def validate_compiled_payload(payload: str, message_format: str) -> OutputValidationReport:
    kind = (message_format or "").lower()
    if kind == "hl7":
        return _hl7_report(payload)
    if kind in {"xml", "hprim", "hprimxml"}:
        return _xml_report(payload)
    if kind in {"fhir", "json"}:
        return _fhir_report(payload)
    return OutputValidationReport(False, "inconnu", [f"Format non supporté: {message_format}"], [])
