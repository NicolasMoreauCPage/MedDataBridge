"""Validation stricte des bundles FHIR (profil France simplifié)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List


@dataclass
class FHIRValidationReport:
    valid: bool
    errors: List[str]
    warnings: List[str]
    resource_count: int
    profile: str = "fr-core"
    strict: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "resource_count": self.resource_count,
            "profile": self.profile,
            "strict": self.strict,
        }


class FHIRProfileValidator:
    """Validateur FHIR orienté Bundle/Patient/Encounter pour interop France."""

    SUPPORTED_BUNDLE_TYPES = {"transaction", "batch", "collection"}
    SUPPORTED_RESOURCE_TYPES = {"Patient", "Encounter", "Location", "Organization"}
    VALID_GENDERS = {"male", "female", "other", "unknown"}
    VALID_ENCOUNTER_STATUS = {
        "planned", "arrived", "triaged", "in-progress", "onleave", "finished", "cancelled"
    }

    def validate_bundle(self, bundle: Dict[str, Any], strict: bool = True, profile: str = "fr-core") -> FHIRValidationReport:
        errors: List[str] = []
        warnings: List[str] = []

        if bundle.get("resourceType") != "Bundle":
            errors.append("Le document doit être un Bundle FHIR")
            return FHIRValidationReport(False, errors, warnings, 0, profile=profile, strict=strict)

        bundle_type = bundle.get("type")
        if bundle_type not in self.SUPPORTED_BUNDLE_TYPES:
            msg = f"Type de bundle '{bundle_type}' non supporté"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        entries = bundle.get("entry", []) or []
        if strict and not entries:
            errors.append("Bundle vide: au moins une entrée est requise en mode strict")

        for idx, entry in enumerate(entries):
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if not resource:
                errors.append(f"Entrée {idx}: ressource manquante")
                continue

            resource_type = resource.get("resourceType")
            if not resource_type:
                errors.append(f"Entrée {idx}: type de ressource manquant")
                continue

            if resource_type not in self.SUPPORTED_RESOURCE_TYPES:
                warnings.append(f"Entrée {idx}: type de ressource '{resource_type}' non pris en charge")
                continue

            if resource_type == "Patient":
                self._validate_patient(resource, idx, errors, warnings, strict)
            elif resource_type == "Encounter":
                self._validate_encounter(resource, idx, errors, warnings, strict)

        return FHIRValidationReport(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            resource_count=len(entries),
            profile=profile,
            strict=strict,
        )

    def _validate_patient(self, patient: Dict[str, Any], idx: int, errors: List[str], warnings: List[str], strict: bool) -> None:
        identifiers = patient.get("identifier") or []
        if strict and not identifiers:
            errors.append(f"Entrée {idx} Patient: identifier requis")
        elif identifiers:
            first = identifiers[0] if isinstance(identifiers[0], dict) else {}
            if not first.get("value"):
                errors.append(f"Entrée {idx} Patient: identifier.value requis")

        names = patient.get("name") or []
        if strict and not names:
            errors.append(f"Entrée {idx} Patient: name requis")
        elif names:
            first_name = names[0] if isinstance(names[0], dict) else {}
            if strict and not first_name.get("family"):
                errors.append(f"Entrée {idx} Patient: name.family requis")
            given = first_name.get("given") or []
            if strict and not given:
                errors.append(f"Entrée {idx} Patient: name.given requis")

        birth_date = patient.get("birthDate")
        if birth_date:
            try:
                date.fromisoformat(birth_date)
            except Exception:
                errors.append(f"Entrée {idx} Patient: birthDate invalide ('{birth_date}')")

        gender = patient.get("gender")
        if gender and gender not in self.VALID_GENDERS:
            errors.append(f"Entrée {idx} Patient: gender invalide ('{gender}')")

    def _validate_encounter(self, encounter: Dict[str, Any], idx: int, errors: List[str], warnings: List[str], strict: bool) -> None:
        status = encounter.get("status")
        if strict and not status:
            errors.append(f"Entrée {idx} Encounter: status requis")
        elif status and status not in self.VALID_ENCOUNTER_STATUS:
            errors.append(f"Entrée {idx} Encounter: status invalide ('{status}')")

        if strict and not encounter.get("class") and not encounter.get("class_"):
            errors.append(f"Entrée {idx} Encounter: class requise")

        subject = encounter.get("subject") or {}
        subject_ref = subject.get("reference") if isinstance(subject, dict) else None
        if strict and not subject_ref:
            errors.append(f"Entrée {idx} Encounter: subject.reference requis")

        period = encounter.get("period") or {}
        if strict and isinstance(period, dict) and not period.get("start"):
            warnings.append(f"Entrée {idx} Encounter: period.start recommandé")
