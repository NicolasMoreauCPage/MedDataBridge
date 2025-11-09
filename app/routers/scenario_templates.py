from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep, InteropScenario, InteropScenarioStep
from app.models_structure_fhir import EntiteJuridique
from app.services.scenario_template_materializer import materialize_template, MaterializationOptions
from app.services.scenario_runner import send_scenario, ScenarioExecutionError
from app.models_endpoints import SystemEndpoint

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/scenarios/templates", tags=["scenario-templates"])


class MaterializeRequest(BaseModel):
    protocol: str = "HL7v2"  # HL7v2 | FHIR
    ej_id: Optional[int] = None
    ipp_prefix: Optional[str] = None
    nda_prefix: Optional[str] = None
    dry_run: bool = True  # si plus tard on veut envoyer directement


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
    templates_q = session.exec(select(ScenarioTemplate).order_by(ScenarioTemplate.name)).all()
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
    return templates.TemplateResponse(request, "list.html", ctx)


@router.get("/{template_key}", response_class=HTMLResponse)
def template_detail(template_key: str, request: Request, session: Session = Depends(get_session)):
    template = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == template_key)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")
    steps = session.exec(
        select(ScenarioTemplateStep)
        .where(ScenarioTemplateStep.template_id == template.id)
        .order_by(ScenarioTemplateStep.order_index)
    ).all()
    # Charger endpoints disponibles pour le formulaire
    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled == True)
        .where(SystemEndpoint.role.in_(["sender", "both"]))
    ).all()
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
    return templates.TemplateResponse(request, "scenario_template_detail.html", ctx)


@router.post("/{template_key}/materialize", response_model=dict)
def materialize(template_key: str, req: MaterializeRequest, session: Session = Depends(get_session)):
    template = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == template_key)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")

    ej: Optional[EntiteJuridique] = None
    if req.ej_id:
        ej = session.get(EntiteJuridique, req.ej_id)
        if not ej:
            raise HTTPException(status_code=404, detail="Entité juridique introuvable")

    options = MaterializationOptions(
        protocol=req.protocol,
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
                "payload_preview": (st.payload[:120] + "…") if len(st.payload) > 120 else st.payload,
            }
            for st in steps
        ],
    }


@router.post("/{template_key}/play", response_model=dict)
async def play_template(
    template_key: str,
    protocol: str = Form("HL7v2"),
    ej_id: Optional[int] = Form(None),
    ipp_prefix: Optional[str] = Form(None),
    nda_prefix: Optional[str] = Form(None),
    endpoint_id: int = Form(...),
    dry_run: bool = Form(True),
    session: Session = Depends(get_session),
):
    template = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == template_key)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    ej: Optional[EntiteJuridique] = None
    if ej_id:
        ej = session.get(EntiteJuridique, ej_id)
        if not ej:
            raise HTTPException(status_code=404, detail="Entité juridique introuvable")
    opts = MaterializationOptions(protocol=protocol, ipp_prefix=ipp_prefix, nda_prefix=nda_prefix)
    scenario = materialize_template(session, template, ej_context=ej, options=opts)
    try:
        logs = await send_scenario(session, scenario, endpoint, dry_run=dry_run)
    except ScenarioExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "run": {
            "scenario_id": scenario.id,
            "endpoint_id": endpoint.id,
            "dry_run": dry_run,
            "message_count": len(logs),
        },
        "messages": [
            {
                "status": lg.status,
                "ack": getattr(lg, "ack_code", None),
                "payload_preview": (lg.payload[:100] + "…") if len(lg.payload) > 100 else lg.payload,
            }
            for lg in logs
        ],
    }
