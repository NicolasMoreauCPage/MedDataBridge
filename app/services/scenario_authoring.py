"""Services du parcours guidé de création de scénarios.

Cette couche assemble les modèles de scénarios existants sans dupliquer le
moteur de matérialisation ni le moteur d'exécution. Un scénario créé depuis
l'assistant est d'abord un brouillon inactif : il ne peut donc pas être envoyé
avant une revue explicite.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from sqlmodel import Session, select

from app.models_endpoints import SystemEndpoint
from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate
from app.models_structure import EntiteJuridique
from app.services.scenario_template_materializer import MaterializationOptions, materialize_template


AUTHORING_DRAFT = "draft"
AUTHORING_READY = "ready"
AUTHORING_PUBLISHED = "published"
AUTHORING_ARCHIVED = "archived"
AUTHORING_STATES = {AUTHORING_DRAFT, AUTHORING_READY, AUTHORING_PUBLISHED, AUTHORING_ARCHIVED}

_ENDPOINT_KINDS_BY_FORMAT = {
    "hl7": {"MLLP", "FILE", "FTP", "SFTP"},
    "fhir": {"FHIR", "FILE", "FTP", "SFTP"},
    "json": {"FILE", "FTP", "SFTP", "FHIR"},
    "xml": {"FILE", "FTP", "SFTP"},
}


@dataclass(frozen=True)
class AuthoringIssue:
    level: str
    code: str
    message: str
    step_id: Optional[int] = None

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "step_id": self.step_id,
        }


def slugify_key(value: str) -> str:
    """Construit une clé lisible, stable et compatible avec les routes/fichiers."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    key = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return key or "scenario"


def unique_scenario_key(session: Session, requested_key: Optional[str], name: str) -> str:
    """Retourne une clé disponible sans imposer à l'utilisateur une convention interne."""
    base = slugify_key(requested_key or name)
    candidate, suffix = base, 2
    while session.exec(select(InteropScenario.id).where(InteropScenario.key == candidate)).first() is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _metadata(source: str, **extra: object) -> str:
    return json.dumps({"source": source, "created_at": datetime.utcnow().isoformat(), **extra}, ensure_ascii=False)


def create_manual_draft(
    session: Session,
    *,
    name: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    protocol: str = "HL7",
    requested_key: Optional[str] = None,
    tags: Optional[str] = None,
) -> InteropScenario:
    scenario = InteropScenario(
        key=unique_scenario_key(session, requested_key, name),
        name=name.strip(),
        description=(description or "").strip() or None,
        category=(category or "").strip() or "CUSTOM",
        protocol=protocol if protocol in {"HL7", "FHIR", "MIXED"} else "HL7",
        tags=(tags or "").strip() or None,
        is_active=False,
        authoring_status=AUTHORING_DRAFT,
        authoring_metadata_json=_metadata("manual"),
    )
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    return scenario


def create_template_draft(
    session: Session,
    *,
    template: ScenarioTemplate,
    name: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    requested_key: Optional[str] = None,
    protocol: str = "HL7v2",
    tags: Optional[str] = None,
    ej_context: Optional[EntiteJuridique] = None,
    ipp_prefix: Optional[str] = None,
    nda_prefix: Optional[str] = None,
) -> InteropScenario:
    if protocol not in {"HL7v2", "FHIR"}:
        raise ValueError("Protocole de modèle invalide : choisir HL7v2 ou FHIR")

    scenario = materialize_template(
        session,
        template,
        ej_context=ej_context,
        options=MaterializationOptions(protocol=protocol, ipp_prefix=ipp_prefix or None, nda_prefix=nda_prefix or None),
    )
    # materialize_template persiste volontairement les payloads concrets. Les
    # attributs éditoriaux sont ensuite adaptés au brouillon de l'utilisateur.
    scenario.key = unique_scenario_key(session, requested_key, name)
    scenario.name = name.strip()
    scenario.description = (description or "").strip() or template.description
    scenario.category = (category or "").strip() or template.category or "CUSTOM"
    scenario.tags = (tags or "").strip() or template.tags
    scenario.is_active = False
    scenario.authoring_status = AUTHORING_DRAFT
    scenario.authoring_metadata_json = _metadata(
        "template",
        template_key=template.key,
        protocol=protocol,
        ipp_prefix=ipp_prefix or None,
        nda_prefix=nda_prefix or None,
    )
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    return scenario


def duplicate_scenario_draft(
    session: Session,
    *,
    source: InteropScenario,
    name: str,
    description: Optional[str] = None,
    requested_key: Optional[str] = None,
) -> InteropScenario:
    duplicate = InteropScenario(
        key=unique_scenario_key(session, requested_key, name),
        name=name.strip(),
        description=(description or "").strip() or source.description,
        functional_comment=source.functional_comment,
        category=source.category,
        protocol=source.protocol,
        preconditions_json=source.preconditions_json,
        assertions_json=source.assertions_json,
        expected_outcome_json=source.expected_outcome_json,
        tags=source.tags,
        is_active=False,
        authoring_status=AUTHORING_DRAFT,
        authoring_metadata_json=_metadata("duplicate", source_scenario_id=source.id),
        ght_context_id=source.ght_context_id,
    )
    session.add(duplicate)
    session.flush()
    for order, step in enumerate(sorted(source.steps, key=lambda item: item.order_index), start=1):
        session.add(
            InteropScenarioStep(
                scenario_id=duplicate.id,
                order_index=order,
                name=step.name,
                description=step.description,
                message_format=step.message_format,
                message_type=step.message_type,
                payload=step.payload,
                delay_seconds=step.delay_seconds,
                is_required=step.is_required,
                route_mode=step.route_mode,
                endpoint_ids_json=step.endpoint_ids_json,
                target_system_key=step.target_system_key,
                assertions_json=step.assertions_json,
            )
        )
    session.commit()
    session.refresh(duplicate)
    return duplicate


def _compatible_endpoint_count(endpoints: Iterable[SystemEndpoint], message_format: str) -> int:
    compatible_kinds = _ENDPOINT_KINDS_BY_FORMAT.get((message_format or "").lower(), set())
    return sum(
        1
        for endpoint in endpoints
        if endpoint.is_enabled
        and endpoint.role in {"sender", "both"}
        and (endpoint.kind or "").upper() in compatible_kinds
    )


def validate_authoring(session: Session, scenario: InteropScenario) -> list[AuthoringIssue]:
    """Valide la préparation sans appeler le moteur d'exécution."""
    issues: list[AuthoringIssue] = []
    if not scenario.name.strip():
        issues.append(AuthoringIssue("error", "scenario.name.required", "Le nom du scénario est obligatoire."))
    if not scenario.key.strip():
        issues.append(AuthoringIssue("error", "scenario.key.required", "La clé du scénario est obligatoire."))

    steps = sorted(scenario.steps, key=lambda item: item.order_index)
    if not steps:
        issues.append(AuthoringIssue("error", "scenario.steps.required", "Ajoutez au moins une étape avant de préparer le scénario."))
        return issues

    endpoints = session.exec(select(SystemEndpoint)).all()
    for step in steps:
        label = step.name or f"Étape {step.order_index}"
        if not step.payload.strip():
            issues.append(AuthoringIssue("error", "step.payload.required", f"{label} ne contient aucun message.", step.id))
        if step.route_mode not in {"all_compatible", "explicit", "target_system"}:
            issues.append(AuthoringIssue("error", "step.route.invalid", f"{label} a un mode de routage inconnu.", step.id))
        elif step.is_required and step.route_mode == "all_compatible" and not _compatible_endpoint_count(endpoints, step.message_format):
            issues.append(
                AuthoringIssue(
                    "warning",
                    "step.route.none_compatible",
                    f"Aucune destination compatible n'est actuellement configurée pour {label}.",
                    step.id,
                )
            )
        elif step.is_required and step.route_mode == "explicit" and not (step.endpoint_ids_json or "").strip():
            issues.append(AuthoringIssue("error", "step.route.required", f"Sélectionnez une destination pour {label}.", step.id))
        elif step.is_required and step.route_mode == "target_system" and not (step.target_system_key or "").strip():
            issues.append(AuthoringIssue("error", "step.target.required", f"Indiquez le système cible de {label}.", step.id))
    return issues


def mark_ready(session: Session, scenario: InteropScenario) -> list[AuthoringIssue]:
    issues = validate_authoring(session, scenario)
    if any(issue.level == "error" for issue in issues):
        return issues
    scenario.authoring_status = AUTHORING_READY
    scenario.is_active = True
    scenario.updated_at = datetime.utcnow()
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    return issues
