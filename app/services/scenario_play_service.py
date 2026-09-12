"""Préparation et émission cohérente des jeux de scénarios multi-protocoles.

Le service est intentionnellement séparé du runner historique: il compile une
fois les messages, alloue une identité unique au jeu, puis réutilise exactement
ces payloads pour tous les endpoints sélectionnés.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlmodel import Session, select

from app.models_endpoints import FHIRConfig, MessageLog, SystemEndpoint
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlay, ScenarioPlayStep, ScenarioPlayTarget
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import IdentifierNamespace
from app.services.fhir_transport import post_fhir_bundle
from app.services.mllp import parse_msh_fields, send_mllp
from app.services.scenario_identifier_replacer import replace_identifiers_in_hl7_message
from app.services.scenario_identity_generator import PatientIdentity, apply_patient_identity_to_hl7, generate_patient_identity
from app.services.scenario_transform import transform_hl7_for_context
from app.services.identifier_generator import generate_identifier_set
from app.services.scenario_qualification_service import refresh_play_target_states, target_key


class ScenarioPlayError(ValueError):
    """Erreur fonctionnelle de préparation ou de livraison d'un jeu."""


def _namespace(session: Session, ght_context_id: Optional[int], kind: str) -> Optional[IdentifierNamespace]:
    if not ght_context_id:
        return None
    return session.exec(
        select(IdentifierNamespace)
        .where(IdentifierNamespace.ght_context_id == ght_context_id)
        .where(IdentifierNamespace.type == kind)
        .where(IdentifierNamespace.is_active == True)  # noqa: E712
        .order_by(IdentifierNamespace.id)
    ).first()


def _identifier_context(session: Session, ght_context_id: Optional[int], play_key: str) -> dict[str, Any]:
    ipp, nda, venue = (_namespace(session, ght_context_id, t) for t in ("IPP", "NDA", "VN"))
    values: dict[str, Optional[str]] = {"ipp": None, "nda": None, "venue": None}
    if ipp and nda:
        values.update(generate_identifier_set(session, ipp, nda, venue))
    # A scenario remains usable in a minimally configured test GHT.  The key is
    # unique and never depends on a timestamp-only value.
    suffix = play_key.rsplit("-", 1)[-1]
    values["ipp"] = values["ipp"] or f"TEST{suffix}"
    values["nda"] = values["nda"] or f"NDA{suffix}"
    values["venue"] = values["venue"] or f"VEN{suffix}"
    return {"identifiers": values, "namespaces": {"ipp": _namespace_dict(ipp), "nda": _namespace_dict(nda), "venue": _namespace_dict(venue)}}


def _namespace_dict(namespace: Optional[IdentifierNamespace]) -> Optional[dict[str, str]]:
    if not namespace:
        return None
    return {"name": namespace.name, "system": namespace.system, "oid": namespace.oid or namespace.system.split(":")[-1]}


def _token_values(play_key: str, identity: PatientIdentity, ids: dict[str, Optional[str]], order: int) -> dict[str, str]:
    now = datetime.utcnow()
    tokens = {
        "{{play.key}}": play_key,
        "{{patient.ipp}}": ids.get("ipp") or "",
        "{{dossier.nda}}": ids.get("nda") or "",
        "{{venue.id}}": ids.get("venue") or "",
        "{{step.order}}": str(order),
        "{{message.control_id}}": f"{play_key}-{order:03d}",
        "{{movement.id}}": f"MVT-{play_key}-{order:03d}",
        "{{patient.family}}": identity.family,
        "{{patient.given}}": identity.given,
        "{{patient.birth_date}}": identity.birth_date.strftime("%Y%m%d"),
        "{{date}}": now.strftime("%Y%m%d"),
        "{{time}}": now.strftime("%H%M%S"),
        "{{uf.code}}": f"UF-{play_key[-6:]}",
        "{{practitioner.rpps}}": "00000000000",
        "{{practitioner.adeli}}": "000000000",
        "{{sender.code}}": "MEDBRIDGE",
        "{{intervention.id}}": f"INT-{play_key[-8:]}",
        "{{act.id}}": f"ACT-{play_key[-8:]}",
        "{{act.code}}": "TEST001",
        "{{care.pathway}}": "oriente",
        "{{organization.code}}": "MEDBRIDGE",
        "{{organization.oid}}": "1.2.250.1.213.1.1.4",
        "{{group.code}}": "GR-TEST",
        "{{billing.value}}": "0",
        "{{beneficiary.name}}": identity.family,
        "{{beneficiary.given}}": identity.given,
        "{{beneficiary.birth_date}}": identity.birth_date.strftime("%Y%m%d"),
    }
    # Les scénarios du pont historique utilisent ces jetons. Les convertir ici
    # permet de rejouer son catalogue sans conserver des identifiants fixes.
    legacy = {
        "$IPP$": "{{patient.ipp}}", "$NIP$": "{{patient.ipp}}", "$NDA$": "{{dossier.nda}}",
        "$VENUE$": "{{venue.id}}", "$UF$": "{{uf.code}}", "$DATE$": "{{date}}", "$HEURE$": "{{time}}",
        "$RPPS$": "{{practitioner.rpps}}", "$ADELI$": "{{practitioner.adeli}}",
        "$NOM$": "{{patient.family}}", "$PRENOM$": "{{patient.given}}",
        "$DOSSIER$": "{{dossier.nda}}", "$EMETTEUR$": "{{sender.code}}", "$INTERVENTION$": "{{intervention.id}}",
        "$IDACTE$": "{{act.id}}", "$ACTE$": "{{act.code}}", "$PSC$": "{{care.pathway}}",
        "$ADELI2$": "{{practitioner.adeli}}", "$ADELI_EXT$": "{{practitioner.adeli}}", "$CODE_SIH$": "{{organization.code}}",
        "$ESPACE_DE_NOM_MEDECIN_SIH$": "{{organization.oid}}", "$GR$": "{{group.code}}", "$UF_EXT$": "{{uf.code}}",
        "$caisse$": "{{billing.value}}", "$centre$": "{{billing.value}}", "$exercice$": "{{billing.value}}", "$finess$": "{{organization.code}}",
        "$montantlot11$": "{{billing.value}}", "$numlot$": "{{billing.value}}", "$numsecu$": "{{billing.value}}", "$numtitre$": "{{billing.value}}",
        "$nombeneficiaire$": "{{beneficiary.name}}", "$prenombeneficiaire$": "{{beneficiary.given}}", "$datenaissance$": "{{beneficiary.birth_date}}", "$datetraitement$": "{{date}}",
    }
    return {**tokens, **{old: tokens[new] for old, new in legacy.items()}}


def _replace_tokens(payload: str, tokens: dict[str, str]) -> str:
    for source, destination in tokens.items():
        payload = payload.replace(source, destination)
    return payload


def _set_hl7_field(payload: str, segment: str, field: int, value: str) -> str:
    lines = payload.replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if line.startswith(f"{segment}|"):
            fields = line.split("|")
            while len(fields) <= field:
                fields.append("")
            fields[field] = value
            lines[index] = "|".join(fields)
            break
    return "\r".join(line for line in lines if line)


def _compile_hl7(
    session: Session,
    scenario: InteropScenario,
    step: InteropScenarioStep,
    payload: str,
    identity: PatientIdentity,
    context: dict[str, Any],
    play_key: str,
) -> str:
    ids = context["identifiers"]
    payload = _replace_tokens(payload, _token_values(play_key, identity, ids, step.order_index))
    try:
        payload = transform_hl7_for_context(session, payload, ght_context_id=scenario.ght_context_id, remap_pid3=False)
    except Exception:
        pass
    payload = apply_patient_identity_to_hl7(payload, identity)
    namespaces = context["namespaces"]
    ipp = _namespace(session, scenario.ght_context_id, "IPP") if namespaces["ipp"] else None
    nda = _namespace(session, scenario.ght_context_id, "NDA") if namespaces["nda"] else None
    venue = _namespace(session, scenario.ght_context_id, "VN") if namespaces["venue"] else None
    if ipp and nda:
        payload, _ = replace_identifiers_in_hl7_message(payload, session, ipp, nda, venue, generated_ids=ids)
    else:
        # A test context without namespaces still uses a stable identity across
        # all HL7 steps in the same play.
        payload = _set_hl7_field(payload, "PID", 3, ids["ipp"] or "")
        payload = _set_hl7_field(payload, "PID", 18, ids["nda"] or "")
        payload = _set_hl7_field(payload, "PV1", 19, ids["nda"] or "")
        payload = _set_hl7_field(payload, "PV1", 50, ids["venue"] or "")
    payload = _set_hl7_field(payload, "MSH", 9, f"{play_key}-{step.order_index:03d}")
    # ZBE-1 identifies the movement in IHE PAM; keeping it deterministic in
    # the play preserves referential integrity without relying on CPage ZBE-9.
    payload = _set_hl7_field(payload, "ZBE", 1, f"MVT-{play_key}-{step.order_index:03d}")
    return payload


def _adapt_fhir(obj: Any, tokens: dict[str, str]) -> Any:
    if isinstance(obj, str):
        return _replace_tokens(obj, tokens)
    if isinstance(obj, list):
        return [_adapt_fhir(item, tokens) for item in obj]
    if not isinstance(obj, dict):
        return obj
    obj = {key: _adapt_fhir(value, tokens) for key, value in obj.items()}
    if obj.get("resourceType") == "Patient":
        identifiers = obj.setdefault("identifier", [])
        if identifiers:
            identifiers[0]["value"] = tokens["{{patient.ipp}}"]
        else:
            identifiers.append({"value": tokens["{{patient.ipp}}"], "type": {"text": "IPP"}})
    if obj.get("resourceType") == "Encounter":
        identifiers = obj.setdefault("identifier", [])
        if identifiers:
            identifiers[0]["value"] = tokens["{{venue.id}}"]
        else:
            identifiers.append({"value": tokens["{{venue.id}}"], "type": {"text": "Venue"}})
    if obj.get("resourceType") == "Bundle":
        obj["id"] = tokens["{{play.key}}"]
    return obj


def _compile_payload(
    session: Session, scenario: InteropScenario, step: InteropScenarioStep, identity: PatientIdentity, context: dict[str, Any], play_key: str
) -> str:
    kind = (step.message_format or "hl7").lower()
    if kind in {"hprim", "hprimxml"}:
        kind = "xml"
    if kind == "hl7":
        return _compile_hl7(session, scenario, step, step.payload, identity, context, play_key)
    tokens = _token_values(play_key, identity, context["identifiers"], step.order_index)
    raw = _replace_tokens(step.payload, tokens)
    if kind in {"fhir", "json"}:
        try:
            return json.dumps(_adapt_fhir(json.loads(raw), tokens), ensure_ascii=False, indent=2)
        except json.JSONDecodeError as exc:
            raise ScenarioPlayError(f"Étape #{step.order_index}: JSON/FHIR invalide: {exc.msg}") from exc
    if kind == "xml":
        # Des exports de l'ancien outil préfixaient parfois le XML par ``MSH|``.
        # Ce n'est pas un segment HPRIM : on le retire avant la validation XML.
        raw = re.sub(r"^\s*MSH\|(?=<)", "", raw)
        return _adapt_hprim_xml(raw, tokens)
    return raw


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _adapt_hprim_xml(payload: str, tokens: dict[str, str]) -> str:
    """Project the common HPRIM identity/message references when XML is valid.

    This deliberately keeps unknown HPRIM extensions untouched. Templates can
    always use explicit tokens; the structural adaptation covers the canonical
    HPRIM patient/venue/message nodes emitted by this application.
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ScenarioPlayError(f"Payload HPRIM XML invalide: {exc}") from exc
    for element in root.iter():
        if _local_name(element.tag) == "identifiantMessage":
            element.text = tokens["{{message.control_id}}"]
    for element in root.iter():
        if _local_name(element.tag) == "patient":
            value = next((node for node in element.iter() if _local_name(node.tag) == "valeur"), None)
            if value is not None:
                value.text = tokens["{{patient.ipp}}"]
        elif _local_name(element.tag) == "venue":
            value = next((node for node in element.iter() if _local_name(node.tag) in {"valeur", "emetteur"}), None)
            if value is not None:
                value.text = tokens["{{venue.id}}"]
    return ET.tostring(root, encoding="unicode")


def _transport_for(endpoint: SystemEndpoint, message_format: str) -> Optional[str]:
    fmt = (message_format or "").lower()
    if fmt in {"hprim", "hprimxml"}:
        fmt = "xml"
    kind = (endpoint.kind or "").upper()
    if fmt == "hl7" and kind == "MLLP":
        return "MLLP"
    if fmt in {"fhir", "json"} and kind == "FHIR":
        return "FHIR"
    if fmt == "xml" and kind in {"HPRIM", "FILE"}:
        return "FILE"
    if kind == "FILE" and fmt in {"hl7", "xml", "json", "fhir"}:
        return "FILE"
    return None


def _fhir_targets(endpoint: SystemEndpoint) -> list[tuple[str, str, Optional[str]]]:
    """Use dedicated FHIR configurations when present, as the historical runner does."""
    configured = [
        (cfg.base_url, cfg.auth_kind or "none", cfg.auth_token)
        for cfg in (getattr(endpoint, "fhir_configs", []) or [])
        if isinstance(cfg, FHIRConfig) and cfg.is_enabled and cfg.base_url
    ]
    if configured:
        return configured
    if endpoint.base_url:
        return [(endpoint.base_url, endpoint.auth_kind or "none", endpoint.auth_token)]
    return []


def prepare_scenario_play(
    session: Session,
    scenario: InteropScenario,
    endpoints: Iterable[SystemEndpoint],
    *,
    dry_run: bool = False,
    step_id: Optional[int] = None,
    start_order_index: Optional[int] = None,
) -> ScenarioPlay:
    """Create a durable play and its compiled, immutable deliveries."""
    targets = list({endpoint.id: endpoint for endpoint in endpoints if endpoint.id is not None}.values())
    if not targets:
        raise ScenarioPlayError("Sélectionnez au moins un endpoint actif.")
    disabled = [endpoint.name for endpoint in targets if not endpoint.is_enabled]
    if disabled:
        raise ScenarioPlayError("Endpoint désactivé : " + ", ".join(disabled))
    play_key = f"PLAY-{uuid4().hex[:12].upper()}"
    identity = generate_patient_identity()
    context = _identifier_context(session, scenario.ght_context_id, play_key)
    context["patient"] = identity.as_dict()
    play = ScenarioPlay(scenario_id=scenario.id, play_key=play_key, ght_context_id=scenario.ght_context_id, dry_run=dry_run, identity_json=json.dumps(context, ensure_ascii=False))
    session.add(play)
    session.flush()
    for endpoint in targets:
        session.add(ScenarioPlayTarget(play_id=play.id, endpoint_id=endpoint.id, target_system_key=target_key(endpoint.target_system_key or endpoint.name)))
    source_steps = sorted(scenario.steps or [], key=lambda item: item.order_index)
    if step_id is not None:
        source_steps = [step for step in source_steps if step.id == step_id]
    elif start_order_index is not None:
        source_steps = [step for step in source_steps if step.order_index >= start_order_index]
    if not source_steps:
        raise ScenarioPlayError("Le scénario ne contient aucune étape à émettre.")
    unsupported = [
        f"#{step.order_index} ({(step.message_format or 'hl7').upper()})"
        for step in source_steps
        if not any(_transport_for(endpoint, step.message_format) for endpoint in targets)
    ]
    if unsupported:
        raise ScenarioPlayError(
            "Aucun endpoint compatible pour les étapes " + ", ".join(unsupported) + ". "
            "Ajoutez une destination adaptée ou limitez les étapes à émettre."
        )
    for step in source_steps:
        payload = _compile_payload(session, scenario, step, identity, context, play_key)
        compatible = [endpoint for endpoint in targets if _transport_for(endpoint, step.message_format)]
        normalized_format = "xml" if (step.message_format or "").lower() in {"hprim", "hprimxml"} else step.message_format
        play_step = ScenarioPlayStep(play_id=play.id, scenario_step_id=step.id, order_index=step.order_index, name=step.name, message_format=normalized_format, message_type=step.message_type, source_payload=step.payload, compiled_payload=payload, routing_json=json.dumps({"compatible_endpoint_ids": [endpoint.id for endpoint in compatible]}))
        session.add(play_step)
        session.flush()
        for endpoint in targets:
            transport = _transport_for(endpoint, step.message_format)
            session.add(ScenarioDelivery(play_id=play.id, play_step_id=play_step.id, endpoint_id=endpoint.id, transport=transport, status="pending" if transport else "skipped", error_message=None if transport else f"{step.message_format.upper()} non compatible avec endpoint {endpoint.kind}"))
    session.commit()
    session.refresh(play)
    return play


async def _send_delivery(session: Session, delivery: ScenarioDelivery, play_step: ScenarioPlayStep, endpoint: SystemEndpoint) -> MessageLog:
    payload, transport = play_step.compiled_payload, delivery.transport
    if transport == "MLLP":
        if not endpoint.host or not endpoint.port:
            raise ScenarioPlayError("Endpoint MLLP incomplet (host/port manquant)")
        ack = await send_mllp(endpoint.host, endpoint.port, payload)
        status = "sent" if "MSA|AE|" not in ack and "MSA|AR|" not in ack else "error"
        log = MessageLog(direction="out", kind="MLLP", endpoint_id=endpoint.id, message_type=play_step.message_type, payload=payload, ack_payload=ack, status=status, correlation_id=parse_msh_fields(payload).get("control_id"))
        if status != "sent":
            raise ScenarioPlayError(f"ACK négatif: {ack[:300]}")
    elif transport == "FHIR":
        targets = _fhir_targets(endpoint)
        if not targets:
            raise ScenarioPlayError("Endpoint FHIR sans base_url")
        code, response, response_text = 0, {}, ""
        for base_url, auth_kind, auth_token in targets:
            code, response = await post_fhir_bundle(base_url, json.loads(payload), auth_kind, auth_token)
            response_text = json.dumps(response or {}, ensure_ascii=False)
            if 200 <= code < 300:
                break
        if not 200 <= code < 300:
            raise ScenarioPlayError(f"FHIR HTTP {code}: {response_text[:300]}")
        log = MessageLog(direction="out", kind="FHIR", endpoint_id=endpoint.id, message_type=play_step.message_type, payload=payload, ack_payload=response_text, status="sent", correlation_id=str(code))
    elif transport == "FILE":
        if not endpoint.outbox_path:
            raise ScenarioPlayError("Endpoint fichier/HPRIM sans répertoire de sortie")
        folder = Path(endpoint.outbox_path)
        folder.mkdir(parents=True, exist_ok=True)
        extension = ".xml" if play_step.message_format.lower() == "xml" else ".hl7" if play_step.message_format.lower() == "hl7" else ".json"
        file_path = folder / f"{delivery.play_id}_{play_step.order_index:03d}_{endpoint.id}{extension}"
        file_path.write_text(payload, encoding="utf-8")
        log = MessageLog(direction="out", kind="HPRIM" if play_step.message_format.lower() == "xml" else "FILE", endpoint_id=endpoint.id, message_type=play_step.message_type, payload=payload, ack_payload=f"FILE:{file_path.name}", status="sent", correlation_id=str(delivery.play_id))
    else:
        raise ScenarioPlayError("Aucun transport compatible pour cette livraison")
    session.add(log)
    session.flush()
    return log


async def execute_scenario_play(session: Session, play_id: int) -> ScenarioPlay:
    """Emit all compatible deliveries in the scenario order and retain evidence."""
    play = session.get(ScenarioPlay, play_id)
    if not play:
        raise ScenarioPlayError("Jeu de scénario introuvable")
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()
    steps = {item.id: item for item in session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).all()}
    endpoints = {item.id: item for item in session.exec(select(SystemEndpoint).where(SystemEndpoint.id.in_([delivery.endpoint_id for delivery in deliveries]))).all()}
    play.started_at, play.status = datetime.utcnow(), "running"
    session.add(play)
    session.commit()
    success, errors = 0, 0
    for delivery in sorted(deliveries, key=lambda item: (steps[item.play_step_id].order_index, item.endpoint_id)):
        delivery.updated_at = datetime.utcnow()
        if play.dry_run:
            delivery.status, delivery.finished_at = ("dry_run" if delivery.status != "skipped" else "skipped"), datetime.utcnow()
            session.add(delivery)
            continue
        if delivery.status == "skipped":
            continue
        delivery.started_at = datetime.utcnow()
        try:
            log = await _send_delivery(session, delivery, steps[delivery.play_step_id], endpoints[delivery.endpoint_id])
            delivery.status, delivery.message_log_id, delivery.ack_code = "sent", log.id, (log.correlation_id or "ACK")
            delivery.response_payload = log.ack_payload
            success += 1
        except Exception as exc:  # preserve an error on one target without aborting all targets
            delivery.status, delivery.error_message = "error", str(exc)[:1000]
            errors += 1
        delivery.finished_at, delivery.updated_at = datetime.utcnow(), datetime.utcnow()
        session.add(delivery)
        session.commit()
    play.finished_at = datetime.utcnow()
    if play.dry_run:
        play.status = "dry_run"
    elif errors and success:
        play.status = "partial"
    elif errors:
        play.status = "error"
    else:
        play.status = "success"
    play.result_json = json.dumps({"sent": success, "errors": errors, "total": len(deliveries)}, ensure_ascii=False)
    play.updated_at = datetime.utcnow()
    session.add(play)
    refresh_play_target_states(session, play.id)
    session.commit()
    return play


async def retry_scenario_delivery(session: Session, delivery_id: int) -> ScenarioDelivery:
    """Retry exactly one delivery with the compiled payload of its original play."""
    delivery = session.get(ScenarioDelivery, delivery_id)
    if not delivery:
        raise ScenarioPlayError("Livraison introuvable")
    if delivery.status == "skipped":
        raise ScenarioPlayError("Une livraison incompatible ne peut pas être rejouée")
    play_step = session.get(ScenarioPlayStep, delivery.play_step_id)
    endpoint = session.get(SystemEndpoint, delivery.endpoint_id)
    if not play_step or not endpoint:
        raise ScenarioPlayError("Étape ou endpoint de livraison introuvable")
    delivery.status, delivery.error_message, delivery.started_at = "pending", None, datetime.utcnow()
    session.add(delivery)
    session.commit()
    try:
        log = await _send_delivery(session, delivery, play_step, endpoint)
        delivery.status, delivery.message_log_id = "sent", log.id
        delivery.ack_code, delivery.response_payload = log.correlation_id or "ACK", log.ack_payload
    except Exception as exc:  # keep the original compiled payload intact for later retry
        delivery.status, delivery.error_message = "error", str(exc)[:1000]
    delivery.finished_at, delivery.updated_at = datetime.utcnow(), datetime.utcnow()
    session.add(delivery)
    refresh_play_target_states(session, delivery.play_id)
    session.commit()
    return delivery


def get_play_details(session: Session, play_id: int) -> tuple[ScenarioPlay, list[ScenarioPlayStep], list[ScenarioDelivery]]:
    play = session.get(ScenarioPlay, play_id)
    if not play:
        raise ScenarioPlayError("Jeu de scénario introuvable")
    return (
        play,
        session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play_id).order_by(ScenarioPlayStep.order_index)).all(),
        session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play_id).order_by(ScenarioDelivery.play_step_id, ScenarioDelivery.endpoint_id)).all(),
    )
