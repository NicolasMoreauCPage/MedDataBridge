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
from datetime import date, datetime
from typing import Iterable, Optional

from sqlmodel import Session, select

from app.models.endpoints import SystemEndpoint
from app.models.scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate
from app.models_structure import EntiteJuridique
from app.services.scenario_template_materializer import (
    MaterializationOptions,
    build_reference_payload,
    materialize_template,
)


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

# Le catalogue est volontairement court : il présente les intentions les plus
# fréquentes au lieu d'exposer tous les codes ADT. Les experts gardent l'accès
# aux types de message et payloads libres dans l'espace historique.
GUIDED_EVENT_CATALOG = (
    {
        "key": "admission_planned",
        "label": "Pré-admission",
        "description": "Patient attendu avant son admission.",
        "semantic_event_code": "ADMISSION_PLANNED",
        "hl7_event_code": "ADT^A05",
        "default_delay_seconds": 0,
    },
    {
        "key": "admission",
        "label": "Admission du patient",
        "description": "Début de l'hospitalisation.",
        "semantic_event_code": "ADMISSION_CONFIRMED",
        "hl7_event_code": "ADT^A01",
        "default_delay_seconds": 0,
    },
    {
        "key": "transfer",
        "label": "Transfert ou mutation",
        "description": "Changement de service, unité ou lit.",
        "semantic_event_code": "TRANSFER_IN",
        "hl7_event_code": "ADT^A02",
        "default_delay_seconds": 300,
    },
    {
        "key": "discharge",
        "label": "Sortie du patient",
        "description": "Fin de l'hospitalisation.",
        "semantic_event_code": "DISCHARGE",
        "hl7_event_code": "ADT^A03",
        "default_delay_seconds": 3600,
    },
    {
        "key": "identity_create",
        "label": "Création de l'identité",
        "description": "Ajout d'une personne dans le système cible.",
        "semantic_event_code": "IDENTITY_CREATED",
        "hl7_event_code": "ADT^A28",
        "default_delay_seconds": 0,
    },
    {
        "key": "identity_update",
        "label": "Mise à jour de l'identité",
        "description": "Modification des informations administratives.",
        "semantic_event_code": "IDENTITY_UPDATED",
        "hl7_event_code": "ADT^A31",
        "default_delay_seconds": 0,
    },
)


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


def guided_event_catalog() -> tuple[dict, ...]:
    """Expose des copies immuables dans l'esprit du catalogue fonctionnel."""
    return GUIDED_EVENT_CATALOG


def _guided_event(event_key: str) -> dict:
    event = next((item for item in GUIDED_EVENT_CATALOG if item["key"] == event_key), None)
    if not event:
        raise ValueError("Événement de parcours inconnu.")
    return event


def _mark_as_edited_draft(scenario: InteropScenario) -> None:
    scenario.authoring_status = AUTHORING_DRAFT
    scenario.is_active = False
    scenario.updated_at = datetime.utcnow()


def authoring_metadata(scenario: InteropScenario) -> dict:
    """Lit les métadonnées guidées sans faire échouer un scénario historique."""
    try:
        value = json.loads(scenario.authoring_metadata_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def common_test_data(scenario: InteropScenario) -> dict[str, str]:
    """Retourne les données communes avec des valeurs de démonstration sûres."""
    data = authoring_metadata(scenario).get("test_data")
    data = data if isinstance(data, dict) else {}
    return {
        "family": str(data.get("family") or "SCENARIO"),
        "given": str(data.get("given") or "Test"),
        "birth_date": str(data.get("birth_date") or "1990-01-15"),
        "gender": str(data.get("gender") or "F"),
    }


def set_common_test_data(
    session: Session,
    *,
    scenario: InteropScenario,
    family: str,
    given: str,
    birth_date: str,
    gender: str,
) -> dict[str, str]:
    """Enregistre une identité de test commune et la soumet à une validation simple."""
    normalized = {
        "family": family.strip().upper(),
        "given": given.strip(),
        "birth_date": birth_date.strip(),
        "gender": gender.strip().upper(),
    }
    if not normalized["family"] or not normalized["given"]:
        raise ValueError("Le nom et le prénom de test sont obligatoires.")
    try:
        date.fromisoformat(normalized["birth_date"])
    except ValueError as exc:
        raise ValueError("La date de naissance doit être au format AAAA-MM-JJ.") from exc
    if normalized["gender"] not in {"F", "M", "U"}:
        raise ValueError("Le sexe administratif doit être F, M ou U.")
    metadata = authoring_metadata(scenario)
    metadata["test_data"] = normalized
    metadata["updated_at"] = datetime.utcnow().isoformat()
    scenario.authoring_metadata_json = json.dumps(metadata, ensure_ascii=False)
    _mark_as_edited_draft(scenario)
    session.add(scenario)
    session.commit()
    return normalized


def guided_assertions_enabled(scenario: InteropScenario) -> bool:
    """Indique si les contrôles standard de préparation sont actifs."""
    try:
        assertions = json.loads(scenario.assertions_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(assertions, list) and any(item.get("source") == "authoring" for item in assertions if isinstance(item, dict))


def set_guided_assertions(session: Session, *, scenario: InteropScenario, enabled: bool) -> None:
    """Ajoute ou retire les assertions gérées par le constructeur.

    Les assertions JSON créées dans le mode expert sont conservées : seules les
    entrées marquées ``source=authoring`` sont régénérées.
    """
    try:
        existing = json.loads(scenario.assertions_json or "[]")
    except (json.JSONDecodeError, TypeError):
        existing = []
    if not isinstance(existing, list):
        existing = []
    preserved = [item for item in existing if isinstance(item, dict) and item.get("source") != "authoring"]
    if enabled:
        preserved.extend(
            {
                "type": "step_status",
                "order_index": step.order_index,
                "equals": "sent",
                "source": "authoring",
                "label": f"Étape {step.order_index} préparée",
            }
            for step in sorted(scenario.steps, key=lambda item: item.order_index)
        )
    scenario.assertions_json = json.dumps(preserved, ensure_ascii=False) if preserved else None
    _mark_as_edited_draft(scenario)
    session.add(scenario)
    session.commit()


def add_guided_step(
    session: Session,
    *,
    scenario: InteropScenario,
    event_key: str,
    message_protocol: Optional[str] = None,
    delay_seconds: Optional[int] = None,
) -> InteropScenarioStep:
    """Ajoute une étape métier générée depuis le catalogue réduit."""
    event = _guided_event(event_key)
    protocol = (message_protocol or scenario.protocol or "HL7").upper()
    if protocol == "MIXED":
        protocol = "HL7"
    next_order = max((step.order_index for step in scenario.steps), default=0) + 1
    payload, message_format, message_type = build_reference_payload(
        semantic_event_code=event["semantic_event_code"],
        protocol=protocol,
        hl7_event_code=event["hl7_event_code"],
        step_index=next_order,
    )
    step = InteropScenarioStep(
        scenario_id=scenario.id,
        order_index=next_order,
        name=event["label"],
        description=event["description"],
        message_format=message_format,
        message_type=message_type,
        payload=payload,
        delay_seconds=event["default_delay_seconds"] if delay_seconds is None else max(delay_seconds, 0),
        is_required=True,
        route_mode="all_compatible",
    )
    _mark_as_edited_draft(scenario)
    session.add(scenario)
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def move_guided_step(session: Session, *, scenario: InteropScenario, step: InteropScenarioStep, direction: str) -> bool:
    """Réordonne une étape sans exposer son index technique à l'interface."""
    ordered = sorted(scenario.steps, key=lambda item: (item.order_index, item.id or 0))
    index = next((position for position, item in enumerate(ordered) if item.id == step.id), None)
    destination = index - 1 if direction == "up" else index + 1 if direction == "down" else None
    if index is None or destination is None or not 0 <= destination < len(ordered):
        return False
    ordered[index], ordered[destination] = ordered[destination], ordered[index]
    for position, item in enumerate(ordered, start=1):
        item.order_index = position
        item.updated_at = datetime.utcnow()
        session.add(item)
    _mark_as_edited_draft(scenario)
    session.add(scenario)
    session.commit()
    return True


def delete_guided_step(session: Session, *, scenario: InteropScenario, step: InteropScenarioStep) -> None:
    """Supprime une étape depuis la revue et maintient un ordre dense."""
    session.delete(step)
    survivors = [item for item in scenario.steps if item.id != step.id]
    for position, item in enumerate(sorted(survivors, key=lambda value: (value.order_index, value.id or 0)), start=1):
        item.order_index = position
        item.updated_at = datetime.utcnow()
        session.add(item)
    _mark_as_edited_draft(scenario)
    session.add(scenario)
    session.commit()


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


def _endpoint_is_compatible(endpoint: SystemEndpoint, message_format: str) -> bool:
    return (
        endpoint.is_enabled
        and endpoint.role in {"sender", "both"}
        and (endpoint.kind or "").upper() in _ENDPOINT_KINDS_BY_FORMAT.get((message_format or "").lower(), set())
    )


def common_compatible_endpoints(session: Session, scenario: InteropScenario) -> list[SystemEndpoint]:
    """Retourne les destinations utilisables pour toutes les étapes du scénario."""
    endpoints = session.exec(select(SystemEndpoint).order_by(SystemEndpoint.kind, SystemEndpoint.name)).all()
    formats = {step.message_format.lower() for step in scenario.steps if step.message_format}
    if not formats:
        return [endpoint for endpoint in endpoints if endpoint.is_enabled and endpoint.role in {"sender", "both"}]
    return [endpoint for endpoint in endpoints if all(_endpoint_is_compatible(endpoint, message_format) for message_format in formats)]


def set_common_routing(
    session: Session,
    *,
    scenario: InteropScenario,
    route_mode: str,
    endpoint_ids: Iterable[int] = (),
) -> None:
    """Applique un routage commun tout en protégeant chaque étape requise."""
    if route_mode not in {"all_compatible", "explicit"}:
        raise ValueError("Mode de routage inconnu.")
    steps = list(scenario.steps)
    endpoint_ids = sorted(set(endpoint_ids))
    endpoints_by_id = {
        endpoint.id: endpoint
        for endpoint in session.exec(select(SystemEndpoint).where(SystemEndpoint.id.in_(endpoint_ids))).all()
    } if endpoint_ids else {}
    if route_mode == "explicit":
        if not endpoint_ids:
            raise ValueError("Sélectionnez au moins une destination.")
        if len(endpoints_by_id) != len(endpoint_ids):
            raise ValueError("Une destination sélectionnée est introuvable.")
        unavailable = [endpoint.name for endpoint in endpoints_by_id.values() if not endpoint.is_enabled or endpoint.role not in {"sender", "both"}]
        if unavailable:
            raise ValueError(f"Destination non disponible : {', '.join(unavailable)}.")
        for step in steps:
            compatible = [endpoint_id for endpoint_id, endpoint in endpoints_by_id.items() if _endpoint_is_compatible(endpoint, step.message_format)]
            if step.is_required and not compatible:
                raise ValueError(f"Aucune destination sélectionnée n'est compatible avec « {step.name or f'étape {step.order_index}'} ».")
            step.route_mode = "explicit"
            step.endpoint_ids_json = json.dumps(compatible)
            step.target_system_key = None
            step.updated_at = datetime.utcnow()
            session.add(step)
    else:
        for step in steps:
            step.route_mode = "all_compatible"
            step.endpoint_ids_json = None
            step.target_system_key = None
            step.updated_at = datetime.utcnow()
            session.add(step)
    _mark_as_edited_draft(scenario)
    session.add(scenario)
    session.commit()


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
