from __future__ import annotations

import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Session, select

from app.db import get_session
from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep
from app.models_structure import EntiteJuridique
from app.services.scenario_template_materializer import (
    materialize_template,
    MaterializationOptions,
)
from app.models.endpoints import SystemEndpoint


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates


router = APIRouter(prefix="/scenarios/templates", tags=["scenario-templates"])

# Ces règles reflètent les transports réellement pris en charge par le moteur
# de jeu (`scenario_play_service._transport_for`). Elles sont vérifiées côté
# serveur, en complément du filtrage ergonomique effectué dans le navigateur.
_PLAYABLE_ENDPOINT_KINDS = {
    "HL7v2": {"MLLP", "FILE", "FTP", "SFTP"},
    "FHIR": {"FHIR", "FILE", "FTP", "SFTP"},
}


class MaterializeRequest(BaseModel):
    protocol: str = "HL7v2"  # HL7v2 | FHIR
    ej_id: Optional[int] = None
    ipp_prefix: Optional[str] = None
    nda_prefix: Optional[str] = None
    dry_run: bool = True  # si plus tard on veut envoyer directement


def _resolve_ej_context(
    request: Request,
    session: Session,
    requested_ej_id: Optional[int],
) -> Optional[EntiteJuridique]:
    """Résout l'EJ demandée sans jamais ignorer le contexte actif."""
    active_ej_id = getattr(getattr(request.state, "ej_context", None), "id", None)
    if requested_ej_id and active_ej_id and requested_ej_id != active_ej_id:
        raise HTTPException(
            status_code=422,
            detail=f"L'entité juridique {requested_ej_id} ne correspond pas au contexte actif ({active_ej_id})",
        )
    ej_id = requested_ej_id or active_ej_id
    if not ej_id:
        return None
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique introuvable")
    return ej


def _validate_play_protocol(protocol: str) -> str:
    if protocol not in _PLAYABLE_ENDPOINT_KINDS:
        raise HTTPException(
            status_code=422,
            detail="Protocole de modèle invalide : choisir HL7v2 ou FHIR",
        )
    return protocol


def _template_to_dict(t: ScenarioTemplate, steps: List[ScenarioTemplateStep]):
    return {
        "id": t.id,
        "key": t.key,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "protocols_supported": t.protocols_supported,
        "tags": t.tags,
        "steps": [
            {
                "id": s.id,
                "order_index": s.order_index,
                "semantic_event_code": s.semantic_event_code,
                "narrative": s.narrative,
                "hl7_event_code": s.hl7_event_code,
                "message_role": s.message_role,
            }
            for s in steps
        ],
    }


@router.get("", response_class=HTMLResponse)
def list_templates(request: Request, session: Session = Depends(get_session)):
    templates_q = session.exec(
        select(ScenarioTemplate).order_by(ScenarioTemplate.name)
    ).all()
    rows = []
    for t in templates_q:
        rows.append(
            {
                "cells": [
                    t.name,
                    t.category or "",
                    t.protocols_supported,
                    len(t.steps or []),
                    t.tags or "",
                ],
                "detail_url": f"/scenarios/templates/{t.key}",
            }
        )
    ctx = {
        "request": request,
        "title": "Templates de scénarios",
        "breadcrumbs": [{"label": "Templates", "url": "/scenarios/templates"}],
        "headers": ["Nom", "Catégorie", "Protocoles", "Étapes", "Tags"],
        "rows": rows,
        "show_actions": False,
    }
    return get_templates_with_filters(request).TemplateResponse(
        request, "list.html", ctx
    )


@router.get("/{template_key}", response_class=HTMLResponse)
def template_detail(
    template_key: str, request: Request, session: Session = Depends(get_session)
):
    template = session.exec(
        select(ScenarioTemplate).where(ScenarioTemplate.key == template_key)
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")
    steps = session.exec(
        select(ScenarioTemplateStep)
        .where(ScenarioTemplateStep.template_id == template.id)
        .order_by(ScenarioTemplateStep.order_index)
    ).all()
    # Charger endpoints disponibles pour le formulaire
    endpoint_query = (
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled)
        .where(SystemEndpoint.role.in_(["sender", "both"]))
        .order_by(SystemEndpoint.kind, SystemEndpoint.name)
    )
    active_ej_id = getattr(getattr(request.state, "ej_context", None), "id", None)
    if active_ej_id:
        endpoint_query = endpoint_query.where(
            or_(
                SystemEndpoint.entite_juridique_id == active_ej_id,
                SystemEndpoint.entite_juridique_id.is_(None),
            )
        )
    endpoints = session.exec(endpoint_query).all()
    ctx = {
        "request": request,
        "template": template,
        "steps": steps,
        "endpoints": endpoints,
        "breadcrumbs": [
            {"label": "Templates", "url": "/scenarios/templates"},
            {"label": template.name, "url": f"/scenarios/templates/{template.key}"},
        ],
    }
    return get_templates_with_filters(request).TemplateResponse(
        request, "scenario_template_detail.html", ctx
    )


@router.post("/{template_key}/materialize", response_model=dict)
def materialize(
    template_key: str,
    req: MaterializeRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    template = session.exec(
        select(ScenarioTemplate).where(ScenarioTemplate.key == template_key)
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")

    protocol = _validate_play_protocol(req.protocol)
    ej = _resolve_ej_context(request, session, req.ej_id)

    options = MaterializationOptions(
        protocol=protocol,
        ipp_prefix=req.ipp_prefix,
        nda_prefix=req.nda_prefix,
    )
    scenario = materialize_template(session, template, ej_context=ej, options=options)
    steps = sorted(scenario.steps, key=lambda s: s.order_index)
    return {
        "scenario": {
            "id": scenario.id,
            "name": scenario.name,
            "protocol": scenario.protocol,
            "category": scenario.category,
            "tags": scenario.tags,
            "step_count": len(steps),
        },
        "steps": [
            {
                "order_index": st.order_index,
                "name": st.name,
                "message_type": st.message_type,
                "message_format": st.message_format,
                "payload_preview": (st.payload[:120] + "…")
                if len(st.payload) > 120
                else st.payload,
            }
            for st in steps
        ],
    }


@router.post("/{template_key}/play", response_model=dict)
def play_template(
    template_key: str,
    request: Request,
    protocol: str = Form("HL7v2"),
    ej_id: Optional[int] = Form(None),
    ipp_prefix: Optional[str] = Form(None),
    nda_prefix: Optional[str] = Form(None),
    endpoint_id: int = Form(...),
    # Une case à cocher absente du formulaire doit bien désactiver la
    # simulation : une valeur par défaut à True la réactiverait à tort.
    dry_run: bool = Form(False),
    session: Session = Depends(get_session),
):
    protocol = _validate_play_protocol(protocol)
    template = session.exec(
        select(ScenarioTemplate).where(ScenarioTemplate.key == template_key)
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    if not endpoint.is_enabled or endpoint.role not in {"sender", "both"}:
        raise HTTPException(
            status_code=422, detail="Cet endpoint n'est pas disponible pour l'émission"
        )
    active_ej_id = getattr(getattr(request.state, "ej_context", None), "id", None)
    if active_ej_id and endpoint.entite_juridique_id not in {None, active_ej_id}:
        raise HTTPException(
            status_code=422,
            detail="Cet endpoint est hors du contexte établissement actif",
        )
    supported_kinds = _PLAYABLE_ENDPOINT_KINDS.get(protocol, set())
    if (endpoint.kind or "").upper() not in supported_kinds:
        raise HTTPException(
            status_code=422,
            detail=f"L'endpoint {endpoint.name} ({endpoint.kind}) n'est pas compatible avec le protocole {protocol}",
        )
    ej = _resolve_ej_context(request, session, ej_id)
    opts = MaterializationOptions(
        protocol=protocol, ipp_prefix=ipp_prefix, nda_prefix=nda_prefix
    )
    scenario = materialize_template(session, template, ej_context=ej, options=opts)
    from app.services.scenario_play_service import (
        ScenarioPlayError,
        execute_scenario_play,
        prepare_scenario_play,
    )

    try:
        play = prepare_scenario_play(session, scenario, [endpoint], dry_run=dry_run)
        play = asyncio.run(execute_scenario_play(session, play.id))
    except ScenarioPlayError as e:
        raise HTTPException(status_code=500, detail=str(e))
    from app.models.scenario_runs import ScenarioDelivery, ScenarioPlayStep

    deliveries = session.exec(
        select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)
    ).all()
    compiled_steps = {
        item.id: item
        for item in session.exec(
            select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)
        ).all()
    }
    return {
        "run": {
            "scenario_id": scenario.id,
            "endpoint_id": endpoint.id,
            "dry_run": dry_run,
            "play_id": play.id,
            "play_key": play.play_key,
            "status": play.status,
            "message_count": len(deliveries),
        },
        "messages": [
            {
                "status": delivery.status,
                "ack": delivery.ack_code,
                "payload_preview": (
                    (
                        delivery.compiled_payload
                        or compiled_steps[delivery.play_step_id].compiled_payload
                    )[:100]
                    + "…"
                )
                if len(
                    delivery.compiled_payload
                    or compiled_steps[delivery.play_step_id].compiled_payload
                )
                > 100
                else (
                    delivery.compiled_payload
                    or compiled_steps[delivery.play_step_id].compiled_payload
                ),
            }
            for delivery in deliveries
        ],
    }
