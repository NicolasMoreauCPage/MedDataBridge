from __future__ import annotations

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import Session, select

from app.db import get_session
from app.models.endpoints import SystemEndpoint
from app.models import Dossier
from app.models.scenarios import (
    InteropScenario,
    InteropScenarioStep,
    ScenarioVersion,
)
from app.models_structure import EntiteJuridique
from app.services.scenario_runner import ScenarioExecutionError, get_scenario
from app.services.scenario_capture import capture_dossier_as_scenario
from app.services.scenario_dashboard import (
    get_scenario_stats,
    get_ack_distribution,
    get_scenario_timeline,
    get_step_error_summary,
    get_scenario_comparison,
)
from app.models.scenario_runs import (
    ScenarioDelivery,
)
from app.models.outbox import OutboundMessage
from app.models.qualification import (
    ScenarioTheme,
    ScenarioThemeAssignment,
)
from app.services.scenario_play_service import (
    ScenarioPlayError,
    execute_scenario_play,
    get_play_details,
    prepare_scenario_play,
    retry_failed_scenario_play,
    retry_scenario_delivery,
)
from app.services.scenario_qualification_service import (
    preflight_issues,
    publication_issues,
)
from app.services.message_diff import semantic_diff
from app.services.scenario_version_service import snapshot_scenario_version
from app.services.scenario_status_service import (
    get_last_scenario_status,
    get_scenarios_status_for_ej,
)
from app.utils.flash import flash
from app.services.scenario_realistic_timeplan import suggest_scenario_timing_update
from app.services.scenario_authoring import (
    AUTHORING_PUBLISHED,
)
from app.state_transitions import SUPPORTED_WORKFLOW_EVENTS

# Glose en langage clair pour les triggers ADT couramment rencontrés dans les
# scénarios mais absents de SUPPORTED_WORKFLOW_EVENTS (pas des transitions de
# workflow "venue", mais des événements d'identité/structure).
_EXTRA_TRIGGER_LABELS = {
    "A08": "Mise à jour informations patient",
    "A28": "Ajout d'une personne (identité)",
    "A31": "Mise à jour d'une personne (identité)",
    "A05": "Pré-admission",
    "A45": "Fusion de mouvement",
    "A47": "Changement d'identifiant patient",
}


def _trigger_labels() -> dict:
    labels = {code: meta["label"] for code, meta in SUPPORTED_WORKFLOW_EVENTS.items()}
    for code, label in _EXTRA_TRIGGER_LABELS.items():
        labels.setdefault(code, label)
    return labels


def _json_int_list(raw: Optional[str]) -> list[int]:
    try:
        value = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return (
        [item for item in value if isinstance(item, int)]
        if isinstance(value, list)
        else []
    )


logger = logging.getLogger(__name__)


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates


router = APIRouter()


@router.get("/{scenario_id}", response_class=HTMLResponse)
def scenario_detail(
    scenario_id: int, request: Request, session: Session = Depends(get_session)
):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")

    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled.is_(True))
        .where(SystemEndpoint.role.in_(["sender", "both"]))
        .order_by(SystemEndpoint.name)
    ).all()

    steps = sorted(scenario.steps, key=lambda s: s.order_index)

    ctx = {
        "request": request,
        "scenario": scenario,
        "steps": steps,
        "endpoints": endpoints,
        "themes": session.exec(
            select(ScenarioTheme)
            .where(ScenarioTheme.is_active.is_(True))
            .order_by(ScenarioTheme.name)
        ).all(),  # noqa: E712
        "current_theme_assignment": session.exec(
            select(ScenarioThemeAssignment)
            .where(ScenarioThemeAssignment.scenario_id == scenario.id)
            .where(ScenarioThemeAssignment.is_primary == True)  # noqa: E712
        ).first(),
        "preflight_issues": preflight_issues(scenario),
        "scenario_versions": session.exec(
            select(ScenarioVersion)
            .where(ScenarioVersion.scenario_id == scenario.id)
            .order_by(ScenarioVersion.version_number.desc())
        ).all(),
        "event_labels": _trigger_labels(),
        "route_endpoint_ids_by_step": {
            step.id: _json_int_list(step.endpoint_ids_json) for step in steps
        },
        "breadcrumbs": [
            {"label": "Scénarios", "url": "/scenarios"},
            {"label": scenario.name, "url": f"/scenarios/{scenario.id}"},
        ],
    }
    return get_templates_with_filters(request).TemplateResponse(
        request, "scenario_detail.html", ctx
    )


@router.post("/{scenario_id}/versions/publish")
def publish_scenario_version(
    scenario_id: int,
    request: Request,
    comment: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    missing = publication_issues(scenario)
    if missing:
        flash(
            request,
            "Publication impossible : " + " ".join(missing),
            level="error",
        )
        return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)
    version = snapshot_scenario_version(
        session, scenario, comment=comment or None, publish=True
    )
    scenario.authoring_status = AUTHORING_PUBLISHED
    scenario.updated_at = datetime.utcnow()
    session.add(scenario)
    session.commit()
    flash(
        request,
        f"Version {version.version_number} publiée et figée pour les prochains jeux.",
        level="success",
    )
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.post("/capture", response_class=RedirectResponse)
def capture_from_dossier(
    request: Request,
    dossier_id: int = Form(...),
    session: Session = Depends(get_session),
):
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    scenario = capture_dossier_as_scenario(session, dossier)
    flash(
        request,
        f"Scénario capturé depuis dossier {dossier.dossier_seq} (id={dossier.id})",
        level="success",
    )
    return RedirectResponse(url=f"/scenarios/{scenario.id}", status_code=303)


@router.post("/{scenario_id}/send")
def scenario_send(
    scenario_id: int,
    request: Request,
    endpoint_ids: list[int] = Form(default=[]),
    endpoint_id: Optional[int] = Form(None),
    step_id: Optional[int] = Form(None),
    dry_run: bool = Form(False),
    start_order_index: Optional[int] = Form(None),
    error_policy: str = Form("continue_other_targets"),
    session: Session = Depends(get_session),
):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    if not scenario.is_active:
        raise HTTPException(
            status_code=409,
            detail="Scénario désactivé : activez-le dans l’administration avant émission.",
        )

    # ``endpoint_id`` stays accepted for bookmarked forms and the public API;
    # the UI now posts endpoint_ids and may select distinct MLLP/FHIR/HPRIM
    # endpoints in a single coherent play.
    selected_ids = list(
        dict.fromkeys(endpoint_ids + ([endpoint_id] if endpoint_id else []))
    )
    endpoints = [
        session.get(SystemEndpoint, selected_id) for selected_id in selected_ids
    ]
    if not endpoints or any(endpoint is None for endpoint in endpoints):
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    endpoints = [endpoint for endpoint in endpoints if endpoint is not None]

    try:
        play = prepare_scenario_play(
            session,
            scenario,
            endpoints,
            dry_run=dry_run,
            step_id=step_id,
            start_order_index=start_order_index,
            error_policy=error_policy,
        )
        play = asyncio.run(execute_scenario_play(session, play.id))
        delivered = session.exec(
            select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)
        ).all()
        if play.status in {"success", "dry_run"}:
            flash(
                request,
                f"Jeu {play.play_key} {'prévisualisé' if dry_run else 'émis'} vers {len(endpoints)} endpoint(s) : {len(delivered)} livraison(s).",
                level="success",
            )
        else:
            flash(
                request,
                f"Jeu {play.play_key} terminé avec le statut {play.status}. Consultez le détail des livraisons.",
                level="warning",
            )
        return RedirectResponse(
            url=f"/scenarios/{scenario_id}/plays/{play.id}", status_code=303
        )
    except (ScenarioExecutionError, ScenarioPlayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{scenario_id}/plays/{play_id}", response_class=HTMLResponse)
def scenario_play_detail(
    scenario_id: int,
    play_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    try:
        play, steps, deliveries = get_play_details(session, play_id)
    except ScenarioPlayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if play.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Jeu hors scénario")
    endpoints = {
        endpoint.id: endpoint
        for endpoint in session.exec(
            select(SystemEndpoint).where(
                SystemEndpoint.id.in_([row.endpoint_id for row in deliveries])
            )
        ).all()
    }
    outbox_by_id = {
        row.id: row
        for row in session.exec(
            select(OutboundMessage).where(
                OutboundMessage.id.in_(
                    [
                        delivery.outbox_id
                        for delivery in deliveries
                        if delivery.outbox_id
                    ]
                )
            )
        ).all()
    }
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "scenario_play_detail.html",
        {
            "request": request,
            "scenario": scenario,
            "play": play,
            "steps": steps,
            "deliveries": deliveries,
            "endpoints_by_id": endpoints,
            "outbox_by_id": outbox_by_id,
            "identity": json.loads(play.identity_json or "{}"),
            "target_context_by_delivery": {
                item.id: json.loads(item.target_context_json or "{}")
                for item in deliveries
            },
            "validation_by_delivery": {
                item.id: json.loads(item.validation_json or "{}") for item in deliveries
            },
            "diffs_by_step": {
                item.id: semantic_diff(
                    item.source_payload, item.compiled_payload, item.message_format
                )
                for item in steps
            },
            "breadcrumbs": [
                {"label": "Scénarios", "url": "/scenarios"},
                {"label": scenario.name, "url": f"/scenarios/{scenario.id}"},
                {"label": play.play_key, "url": ""},
            ],
        },
    )


@router.get("/{scenario_id}/plays/{play_id}/diagnostic.json")
def scenario_play_diagnostic(
    scenario_id: int, play_id: int, session: Session = Depends(get_session)
):
    """Preuve portable : payloads, routage, réponses et tentatives d'un jeu."""
    play, steps, deliveries = get_play_details(session, play_id)
    if play.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Jeu hors scénario")
    outbox = {
        row.id: row
        for row in session.exec(
            select(OutboundMessage).where(
                OutboundMessage.id.in_(
                    [item.outbox_id for item in deliveries if item.outbox_id]
                )
            )
        ).all()
    }
    return {
        "play_key": play.play_key,
        "status": play.status,
        "error_policy": play.error_policy,
        "started_at": play.started_at,
        "finished_at": play.finished_at,
        "scenario_version_id": play.scenario_version_id,
        "identity": json.loads(play.identity_json or "{}"),
        "steps": [
            {
                "order": item.order_index,
                "format": item.message_format,
                "required": item.is_required,
                "delay_seconds": item.delay_seconds,
                "source": item.source_payload,
                "compiled": item.compiled_payload,
            }
            for item in steps
        ],
        "deliveries": [
            {
                "id": item.id,
                "step_id": item.play_step_id,
                "endpoint_id": item.endpoint_id,
                "transport": item.transport,
                "required": item.is_required,
                "status": item.status,
                "scheduled_at": item.scheduled_at,
                "ack": item.ack_code,
                "response": item.response_payload,
                "error": item.error_message,
                "validation_status": item.validation_status,
                "validation": json.loads(item.validation_json or "{}"),
                "compiled_payload": item.compiled_payload,
                "target_context": json.loads(item.target_context_json or "{}"),
                "outbox": {
                    "id": outbox[item.outbox_id].id,
                    "status": outbox[item.outbox_id].status,
                    "attempts": outbox[item.outbox_id].attempts,
                    "next_attempt_at": outbox[item.outbox_id].next_attempt_at,
                    "last_error": outbox[item.outbox_id].last_error,
                }
                if item.outbox_id in outbox
                else None,
            }
            for item in deliveries
        ],
    }


@router.post("/{scenario_id}/plays/{play_id}/deliveries/{delivery_id}/retry")
async def scenario_delivery_retry(
    scenario_id: int,
    play_id: int,
    delivery_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Technical retry: preserve the exact compiled payload and identifiers."""
    try:
        play, _, _ = get_play_details(session, play_id)
        if play.scenario_id != scenario_id:
            raise ScenarioPlayError("Jeu hors scénario")
        delivery = await retry_scenario_delivery(session, delivery_id)
    except ScenarioPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    flash(
        request,
        f"Livraison #{delivery.id} {'envoyée' if delivery.status == 'sent' else 'en erreur'} avec le même jeu.",
        level="success" if delivery.status == "sent" else "warning",
    )
    return RedirectResponse(
        url=f"/scenarios/{scenario_id}/plays/{play_id}", status_code=303
    )


@router.post("/{scenario_id}/plays/{play_id}/retry-failed")
async def scenario_play_retry_failed(
    scenario_id: int,
    play_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Reprend le reliquat d'un jeu sans jamais régénérer son identité."""
    try:
        play, _, _ = get_play_details(session, play_id)
        if play.scenario_id != scenario_id:
            raise ScenarioPlayError("Jeu hors scénario")
        play = await retry_failed_scenario_play(session, play_id)
    except ScenarioPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    level = "success" if play.status == "success" else "warning"
    flash(
        request,
        f"Reprise du jeu {play.play_key} terminée : {play.status}.",
        level=level,
    )
    return RedirectResponse(
        url=f"/scenarios/{scenario_id}/plays/{play_id}", status_code=303
    )


# --- JSON export endpoints (added) ---
@router.get("/{scenario_id}/export")
def export_scenario_json(scenario_id: int, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    steps = [
        {
            "order_index": s.order_index,
            "name": s.name,
            "description": s.description,
            "message_type": s.message_type,
            "format": s.message_format,
            "delay_seconds": s.delay_seconds,
            "is_required": s.is_required,
            "route_mode": s.route_mode,
            "endpoint_ids": json.loads(s.endpoint_ids_json or "[]"),
            "target_system_key": s.target_system_key,
            "payload": s.payload,
            "assertions_json": s.assertions_json,
        }
        for s in sorted(scenario.steps, key=lambda st: st.order_index)
    ]
    return {
        "id": scenario.id,
        "key": scenario.key,
        "name": scenario.name,
        "description": scenario.description,
        "functional_comment": scenario.functional_comment,
        "protocol": scenario.protocol,
        "tags": scenario.tags,
        "preconditions_json": scenario.preconditions_json,
        "assertions_json": scenario.assertions_json,
        "expected_outcome_json": scenario.expected_outcome_json,
        "time_config": {
            "anchor_mode": scenario.time_anchor_mode,
            "anchor_days_offset": scenario.time_anchor_days_offset,
            "fixed_start_iso": scenario.time_fixed_start_iso,
            "preserve_intervals": scenario.preserve_intervals,
            "jitter_min": scenario.jitter_min_minutes,
            "jitter_max": scenario.jitter_max_minutes,
            "jitter_events": scenario.apply_jitter_on_events,
        },
        "steps": steps,
    }


@router.get("/api/stats")
def get_stats(
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    session: Session = Depends(get_session),
):
    """Statistiques globales d'exécution."""
    return get_scenario_stats(session, scenario_id, endpoint_id, days_back)


@router.get("/api/ack-distribution")
def get_ack_dist(
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    session: Session = Depends(get_session),
):
    """Distribution des codes ACK."""
    return get_ack_distribution(session, scenario_id, endpoint_id, days_back)


@router.get("/api/timeline")
def get_timeline(
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    session: Session = Depends(get_session),
):
    """Timeline d'exécutions par jour."""
    return get_scenario_timeline(session, scenario_id, endpoint_id, days_back)


@router.get("/api/comparison")
def get_comparison(
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    limit: int = 10,
    session: Session = Depends(get_session),
):
    """Comparaison de performances entre scénarios."""
    return get_scenario_comparison(session, endpoint_id, days_back, limit)


@router.get("/api/run/{run_id}/errors")
def get_run_errors(run_id: int, session: Session = Depends(get_session)):
    """Détail des erreurs pour un run spécifique."""
    return get_step_error_summary(session, run_id)


@router.get("/api/scenario/{scenario_id}/status")
def get_scenario_status_api(
    scenario_id: int,
    endpoint_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """Récupère le statut du dernier run d'un scénario."""
    status = get_last_scenario_status(session, scenario_id, endpoint_id=endpoint_id)
    return {
        "scenario_id": status.scenario_id,
        "scenario_name": status.scenario_name,
        "status": status.status,
        "ack_code": status.ack_code,
        "is_success": status.is_success,
        "has_errors": status.has_errors,
        "visual_indicator": status.visual_indicator,
        "last_run_at": status.last_run_at.isoformat() if status.last_run_at else None,
        "success_steps": status.success_steps,
        "total_steps": status.total_steps,
    }


@router.get("/ej-status", response_class=HTMLResponse)
def ej_scenarios_status(
    request: Request,
    ej_id: Optional[int] = None,
    only_failed: bool = False,
    session: Session = Depends(get_session),
):
    """Affiche l'état des scénarios pour chaque EJ avec filtrage des erreurs."""

    # Récupérer toutes les EJ
    ej_list = session.exec(select(EntiteJuridique).order_by(EntiteJuridique.name)).all()

    scenarios = []
    stats = {
        "total_scenarios": 0,
        "success_scenarios": 0,
        "partial_scenarios": 0,
        "error_scenarios": 0,
    }

    if ej_id:
        # Récupérer les statuts pour cette EJ
        scenarios = get_scenarios_status_for_ej(session, ej_id, only_failed=only_failed)

        # Calculer les stats
        stats["total_scenarios"] = len(scenarios)
        stats["success_scenarios"] = len([s for s in scenarios if s.is_success])
        stats["partial_scenarios"] = len([s for s in scenarios if s.is_partial])
        stats["error_scenarios"] = len(
            [s for s in scenarios if s.has_errors and not s.is_partial]
        )

    ctx = {
        "request": request,
        "breadcrumbs": [
            {"label": "Scénarios", "url": "/scenarios"},
            {"label": "Par EJ", "url": "/scenarios/ej-status"},
        ],
        "ej_list": ej_list,
        "selected_ej_id": ej_id,
        "scenarios": scenarios,
        "stats": stats,
        "only_failed": only_failed,
    }
    return get_templates_with_filters(request).TemplateResponse(
        request, "scenarios/ej_scenarios_status.html", ctx
    )


@router.get("/api/ej/{ej_id}/scenarios-status")
def get_ej_scenarios_status(
    ej_id: int, only_failed: bool = False, session: Session = Depends(get_session)
):
    """Récupère le statut de tous les scénarios pour une EJ donnée.

    Query params:
    - only_failed: bool (défaut=false) - Retourner seulement les scénarios échoués
    """
    statuses = get_scenarios_status_for_ej(session, ej_id, only_failed=only_failed)

    return {
        "ej_id": ej_id,
        "count": len(statuses),
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "scenario_name": s.scenario_name,
                "status": s.status,
                "ack_code": s.ack_code,
                "is_success": s.is_success,
                "has_errors": s.has_errors,
                "visual_indicator": s.visual_indicator,
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                "success_steps": s.success_steps,
                "total_steps": s.total_steps,
            }
            for s in statuses
        ],
    }


@router.post("/{scenario_id}/suggest-realistic-timing")
def suggest_realistic_timing(scenario_id: int, session: Session = Depends(get_session)):
    """Suggère une configuration temporelle réaliste pour un scénario basée sur l'analyse de ses messages HL7."""
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Récupérer les messages HL7 du scénario
    hl7_steps = session.exec(
        select(InteropScenarioStep)
        .where(InteropScenarioStep.scenario_id == scenario_id)
        .where(InteropScenarioStep.message_format.ilike("hl7"))
        .order_by(InteropScenarioStep.order_index)
    ).all()

    if not hl7_steps:
        raise HTTPException(status_code=400, detail="No HL7 messages found in scenario")

    messages = [step.payload for step in hl7_steps]
    message_types = [step.message_type for step in hl7_steps]

    # Générer la suggestion
    suggestion = suggest_scenario_timing_update(scenario_id, messages, message_types)

    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario.name,
        "current_config": {
            "time_anchor_mode": scenario.time_anchor_mode,
            "time_anchor_days_offset": scenario.time_anchor_days_offset,
            "preserve_intervals": scenario.preserve_intervals,
            "jitter_min_minutes": scenario.jitter_min_minutes,
            "jitter_max_minutes": scenario.jitter_max_minutes,
            "apply_jitter_on_events": scenario.apply_jitter_on_events,
        },
        "suggested_config": {
            k: v for k, v in suggestion.items() if not k.startswith("_")
        },
        "analysis": {
            "detected_workflow": suggestion.get("_detected_workflow"),
            "workflow_description": suggestion.get("_workflow_description"),
            "event_sequence": suggestion.get("_event_sequence"),
        },
    }


@router.post("/{scenario_id}/apply-realistic-timing")
def apply_realistic_timing(scenario_id: int, session: Session = Depends(get_session)):
    """Applique automatiquement une configuration temporelle réaliste à un scénario."""
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Récupérer les messages HL7 du scénario
    hl7_steps = session.exec(
        select(InteropScenarioStep)
        .where(InteropScenarioStep.scenario_id == scenario_id)
        .where(InteropScenarioStep.message_format.ilike("hl7"))
        .order_by(InteropScenarioStep.order_index)
    ).all()

    if not hl7_steps:
        raise HTTPException(status_code=400, detail="No HL7 messages found in scenario")

    messages = [step.payload for step in hl7_steps]
    message_types = [step.message_type for step in hl7_steps]

    # Générer et appliquer la suggestion
    suggestion = suggest_scenario_timing_update(scenario_id, messages, message_types)

    # Mettre à jour le scénario avec la nouvelle configuration
    scenario.time_anchor_mode = suggestion.get("time_anchor_mode")
    scenario.time_anchor_days_offset = suggestion.get("time_anchor_days_offset")
    scenario.preserve_intervals = suggestion.get("preserve_intervals")
    scenario.jitter_min_minutes = suggestion.get("jitter_min_minutes")
    scenario.jitter_max_minutes = suggestion.get("jitter_max_minutes")
    scenario.apply_jitter_on_events = suggestion.get("apply_jitter_on_events")

    session.add(scenario)
    session.commit()
    session.refresh(scenario)

    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario.name,
        "applied_config": {
            "time_anchor_mode": scenario.time_anchor_mode,
            "time_anchor_days_offset": scenario.time_anchor_days_offset,
            "preserve_intervals": scenario.preserve_intervals,
            "jitter_min_minutes": scenario.jitter_min_minutes,
            "jitter_max_minutes": scenario.jitter_max_minutes,
            "apply_jitter_on_events": scenario.apply_jitter_on_events,
        },
        "analysis": {
            "detected_workflow": suggestion.get("_detected_workflow"),
            "workflow_description": suggestion.get("_workflow_description"),
            "event_sequence": suggestion.get("_event_sequence"),
        },
        "success": True,
        "message": f"Configuration temporelle réaliste appliquée avec succès (workflow: {suggestion.get('_detected_workflow')})",
    }
