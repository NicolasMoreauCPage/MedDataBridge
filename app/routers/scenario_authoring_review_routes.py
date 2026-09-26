"""Routes de revue du créateur guidé de scénarios.

Séparées du catalogue et des campagnes pour maintenir les parcours de création
lisibles et testables indépendamment.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models.endpoints import SystemEndpoint
from app.services.scenario_authoring import (
    common_compatible_endpoints,
    common_test_data,
    guided_assertions_enabled,
    guided_event_catalog,
    validate_authoring,
)
from app.services.scenario_runner import get_scenario


router = APIRouter(tags=["scenario-authoring"])


def _json_int_list(raw: str | None) -> list[int]:
    try:
        value = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return [item for item in value if isinstance(item, int)] if isinstance(value, list) else []


@router.get("/{scenario_id}/authoring", response_class=HTMLResponse)
def scenario_authoring_review(
    scenario_id: int, request: Request, session: Session = Depends(get_session)
):
    """Affiche la revue légère d'un brouillon avant son exécution."""
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    steps = sorted(scenario.steps, key=lambda step: step.order_index)
    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled.is_(True))
        .where(SystemEndpoint.role.in_(["sender", "both"]))
        .order_by(SystemEndpoint.kind, SystemEndpoint.name)
    ).all()
    compatible_kinds = {
        "hl7": {"MLLP", "FILE", "FTP", "SFTP"},
        "fhir": {"FHIR", "FILE", "FTP", "SFTP"},
        "json": {"FHIR", "FILE", "FTP", "SFTP"},
        "xml": {"FILE", "FTP", "SFTP"},
    }
    endpoint_counts = {
        step.id: sum(
            1
            for endpoint in endpoints
            if (endpoint.kind or "").upper()
            in compatible_kinds.get(step.message_format.lower(), set())
        )
        for step in steps
    }
    explicit_ids = {
        tuple(_json_int_list(step.endpoint_ids_json))
        for step in steps
        if step.route_mode == "explicit"
    }
    common_routing = {
        "mode": "explicit" if steps and all(step.route_mode == "explicit" for step in steps) else "all_compatible",
        "endpoint_ids": list(explicit_ids.pop()) if len(explicit_ids) == 1 else [],
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "scenario_authoring_review.html",
        {
            "request": request,
            "scenario": scenario,
            "steps": steps,
            "issues": [issue.as_dict() for issue in validate_authoring(session, scenario)],
            "endpoint_counts": endpoint_counts,
            "common_endpoints": common_compatible_endpoints(session, scenario),
            "common_routing": common_routing,
            "test_data": common_test_data(scenario),
            "guided_assertions_enabled": guided_assertions_enabled(scenario),
            "guided_events": guided_event_catalog(),
            "available_message_protocols": [
                {"value": "HL7", "label": "HL7 v2"},
                {"value": "FHIR", "label": "FHIR R4"},
            ] if scenario.protocol == "MIXED" else [],
            "breadcrumbs": [
                {"label": "Scénarios", "url": "/scenarios"},
                {"label": "Nouveau scénario", "url": "/scenarios/new"},
                {"label": "Revue", "url": f"/scenarios/{scenario.id}/authoring"},
            ],
        },
    )
