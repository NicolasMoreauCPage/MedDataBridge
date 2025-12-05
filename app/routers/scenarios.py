from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import Session, select

from app.db import get_session
from app.models_endpoints import SystemEndpoint
from app.models import Dossier
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import GHTContext
from app.services.scenario_runner import ScenarioExecutionError, get_scenario, send_scenario, send_step
from app.services.scenario_capture import capture_dossier_as_scenario
from app.services.scenario_import import import_scenario_from_json, validate_scenario_json, ScenarioImportError
from app.services.scenario_dashboard import (
    get_scenario_stats,
    get_ack_distribution,
    get_scenario_timeline,
    get_step_error_summary,
    get_scenario_comparison
)
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.services.scenario_status_service import (
    get_last_scenario_status,
    get_scenarios_status_for_ej,
    get_scenarios_with_status,
)
from app.utils.flash import flash


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_class=HTMLResponse)
def list_scenarios(
    request: Request,
    filter_status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Liste les scénarios avec leur dernier statut d'exécution."""
    
    # Récupérer les scénarios avec statut
    scenarios_data = get_scenarios_with_status(session, filter_by_status=filter_status)
    
    rows = []
    for scenario, status in scenarios_data:
        rows.append(
            {
                "cells": [
                    status.visual_indicator,
                    scenario.name,
                    scenario.protocol,
                    len(scenario.steps or []),
                    status.ack_code or "—",
                    status.last_run_at.strftime("%Y-%m-%d %H:%M") if status.last_run_at else "—",
                ],
                "detail_url": f"/scenarios/{scenario.id}",
                "css_class": status.css_class,
            }
        )

    ctx = {
        "request": request,
        "title": "Scénarios d'interopération",
        "breadcrumbs": [{"label": "Scénarios", "url": "/scenarios"}],
        "headers": ["", "Nom", "Protocole", "Étapes", "Dernier ACK", "Dernière exécution"],
        "rows": rows,
        "show_actions": True,
        "actions": [
            {"label": "Importer", "url": "/scenarios/import", "icon": "upload"}
        ],
        "filter_status": filter_status,
        "filter_options": [
            {"label": "Tous", "value": None},
            {"label": "✅ Succès (tous AA)", "value": "all_aa"},
            {"label": "⚠️  Partiel (certains AA)", "value": "some_aa"},
            {"label": "❌ Erreurs", "value": "error"},
            {"label": "⏹️  Jamais exécutés", "value": "no_run"},
        ],
    }
    return get_templates_with_filters(request).TemplateResponse(request, "list.html", ctx)


@router.get("/runs.json")
def list_runs_json(session: Session = Depends(get_session)):
    """Export JSON des dernières exécutions."""
    runs = session.exec(
        select(ScenarioExecutionRun).order_by(ScenarioExecutionRun.started_at.desc()).limit(200)
    ).all()
    return [
        {
            "id": r.id,
            "scenario_id": r.scenario_id,
            "endpoint_id": r.endpoint_id,
            "status": r.status,
            "success_steps": r.success_steps,
            "error_steps": r.error_steps,
            "skipped_steps": r.skipped_steps,
            "total_steps": r.total_steps,
            "dry_run": r.dry_run,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in runs
    ]


@router.get("/runs", response_class=HTMLResponse)
def list_runs(
    request: Request,
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    status: Optional[str] = None,
    days_back: int = 30,
    session: Session = Depends(get_session)
):
    # Statistiques globales
    stats = get_scenario_stats(session, scenario_id, endpoint_id, days_back)
    ack_dist = get_ack_distribution(session, scenario_id, endpoint_id, days_back)
    
    # Liste des runs filtrée
    query = select(ScenarioExecutionRun).order_by(ScenarioExecutionRun.started_at.desc())
    
    if scenario_id:
        query = query.where(ScenarioExecutionRun.scenario_id == scenario_id)
    if endpoint_id:
        query = query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    if status:
        query = query.where(ScenarioExecutionRun.status == status)
    
    runs = session.exec(query.limit(100)).all()
    rows = []
    for run in runs:
        rows.append(
            {
                "cells": [
                    f"Run #{run.id}",
                    run.status,
                    f"{run.success_steps}/{run.total_steps}",
                    "dry" if run.dry_run else "real",
                    run.finished_at.strftime("%H:%M:%S") if run.finished_at else "—",
                ],
                "detail_url": f"/scenarios/runs/{run.id}",
            }
        )
    
    # Options de filtres
    scenarios = session.exec(select(InteropScenario)).all()
    endpoints = session.exec(select(SystemEndpoint)).all()
    
    ctx = {
        "request": request,
        "title": "Dashboard Exécutions",
        "breadcrumbs": [
            {"label": "Scénarios", "url": "/scenarios"},
            {"label": "Dashboard", "url": "/scenarios/runs"},
        ],
        "headers": ["Run", "Statut", "Succès", "Mode", "Fin"],
        "rows": rows,
        "show_actions": False,
        "stats": stats,
        "ack_distribution": ack_dist,
        "scenarios": scenarios,
        "endpoints": endpoints,
        "filters": {
            "scenario_id": scenario_id,
            "endpoint_id": endpoint_id,
            "status": status,
            "days_back": days_back,
        }
    }
    return get_templates_with_filters(request).TemplateResponse(request, "scenarios/dashboard.html", ctx)


# --- Import routes (must be before /{scenario_id} to avoid conflicts) ---
@router.get("/import", response_class=HTMLResponse)
def show_import_form(request: Request, session: Session = Depends(get_session)):
    """Display the scenario import form."""
    contexts = session.exec(select(GHTContext).order_by(GHTContext.name)).all()
    ctx = {
        "request": request,
        "contexts": contexts,
    }
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_import.html", ctx)


@router.post("/import")
async def import_scenario(
    request: Request,
    ght_context_id: int = Form(...),
    override_key: Optional[str] = Form(None),
    override_name: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    """Import scenario from JSON export."""
    try:
        form_data = await request.form()
        json_file = form_data.get("json_file")
        
        if json_file:
            content = await json_file.read()
            json_data = json.loads(content.decode("utf-8"))
        else:
            json_text = form_data.get("json_data")
            if not json_text:
                flash(request, "Aucune donnée JSON fournie", level="error")
                return RedirectResponse(url="/scenarios", status_code=303)
            json_data = json.loads(json_text)
        
        is_valid, error_msg = validate_scenario_json(json_data)
        if not is_valid:
            flash(request, f"JSON invalide: {error_msg}", level="error")
            return RedirectResponse(url="/scenarios", status_code=303)
        
        scenario = import_scenario_from_json(
            session, 
            json_data, 
            ght_context_id,
            override_key=override_key,
            override_name=override_name
        )
        
        flash(
            request, 
            f"Scénario '{scenario.name}' importé avec succès ({len(scenario.steps)} étapes)",
            level="success"
        )
        return RedirectResponse(url=f"/scenarios/{scenario.id}", status_code=303)
        
    except json.JSONDecodeError as e:
        flash(request, f"Erreur de parsing JSON: {str(e)}", level="error")
        return RedirectResponse(url="/scenarios", status_code=303)
    except ScenarioImportError as e:
        flash(request, f"Erreur d'import: {str(e)}", level="error")
        return RedirectResponse(url="/scenarios", status_code=303)
    except Exception as e:
        flash(request, f"Erreur inattendue: {str(e)}", level="error")
        return RedirectResponse(url="/scenarios", status_code=303)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: int, request: Request, session: Session = Depends(get_session)):
    run = session.get(ScenarioExecutionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run introuvable")
    # Charger logs d'étapes
    step_logs = session.exec(
        select(ScenarioExecutionStepLog)
        .where(ScenarioExecutionStepLog.run_id == run.id)
        .order_by(ScenarioExecutionStepLog.order_index)
    ).all()
    rows = []
    for log in step_logs:
        rows.append(
            {
                "cells": [
                    f"#{log.order_index}",
                    log.status,
                    log.ack_code or "",
                    (str(log.duration_ms) + " ms") if log.duration_ms else "",
                    (log.error_message[:60] + "…") if log.error_message else "",
                ],
                "detail_url": None,
            }
        )
    ctx = {
        "request": request,
        "title": f"Run #{run.id} - Scénario {run.scenario_id}",
        "breadcrumbs": [
            {"label": "Scénarios", "url": "/scenarios"},
            {"label": "Runs", "url": "/scenarios/runs"},
            {"label": f"Run {run.id}", "url": f"/scenarios/runs/{run.id}"},
        ],
        "headers": ["Étape", "Statut", "ACK", "Durée", "Erreur"],
        "rows": rows,
        "show_actions": False,
    }
    return get_templates_with_filters(request).TemplateResponse(request, "list.html", ctx)


@router.get("/{scenario_id}", response_class=HTMLResponse)
def scenario_detail(scenario_id: int, request: Request, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")

    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled == True)
        .where(SystemEndpoint.role.in_(["sender", "both"]))
        .order_by(SystemEndpoint.name)
    ).all()

    steps = sorted(scenario.steps, key=lambda s: s.order_index)

    ctx = {
        "request": request,
        "scenario": scenario,
        "steps": steps,
        "endpoints": endpoints,
        "breadcrumbs": [
            {"label": "Scénarios", "url": "/scenarios"},
            {"label": scenario.name, "url": f"/scenarios/{scenario.id}"},
        ],
    }
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_detail.html", ctx)


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
    flash(request, f"Scénario capturé depuis dossier {dossier.dossier_seq} (id={dossier.id})", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario.id}", status_code=303)



@router.post("/{scenario_id}/send")
async def scenario_send(
    scenario_id: int,
    request: Request,
    endpoint_id: int = Form(...),
    step_id: Optional[int] = Form(None),
    dry_run: bool = Form(False),
    start_order_index: Optional[int] = Form(None),
    session: Session = Depends(get_session),
):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")

    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")

    try:
        if step_id:
            step = session.get(InteropScenarioStep, step_id)
            if not step:
                raise HTTPException(status_code=404, detail="Étape introuvable")
            log = await send_step(session, step, endpoint)
            if log.status == "sent":
                level = "success"
            elif log.status == "skipped":
                level = "info"
            else:
                level = "warning"
            flash(
                request,
                f"Étape #{step.order_index} envoyée vers {endpoint.name} (statut {log.status}).",
                level=level,
            )
        else:
            logs = await send_scenario(
                session,
                scenario,
                endpoint,
                dry_run=dry_run,
                start_order_index=start_order_index,
            )
            errors = [log for log in logs if log.status not in {"sent", "skipped"}]
            skipped = [log for log in logs if log.status == "skipped"]
            if errors:
                flash(
                    request,
                    f"Scénario {scenario.name} envoyé avec {len(errors)} messages en anomalie.",
                    level="warning",
                )
            elif skipped:
                flash(
                    request,
                    f"Scénario {scenario.name} exécuté ({len(logs)} messages, {len(skipped)} ignorés car Zxx).",
                    level="info",
                )
            else:
                flash(
                    request,
                    f"Scénario {scenario.name} envoyé avec succès ({len(logs)} messages).",
                    level="success",
                )
    except ScenarioExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RedirectResponse(url=f"/scenarios/{scenario_id}?sent=1", status_code=303)

# --- JSON export endpoints (added) ---
@router.get("/{scenario_id}/export")
def export_scenario_json(scenario_id: int, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    steps = [
        {
            "order_index": s.order_index,
            "message_type": s.message_type,
            "format": s.message_format,
            "delay_seconds": s.delay_seconds,
            "payload": s.payload,
        }
        for s in sorted(scenario.steps, key=lambda st: st.order_index)
    ]
    return {
        "id": scenario.id,
        "key": scenario.key,
        "name": scenario.name,
        "description": scenario.description,
        "protocol": scenario.protocol,
        "tags": scenario.tags,
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
    session: Session = Depends(get_session)
):
    """Statistiques globales d'exécution."""
    return get_scenario_stats(session, scenario_id, endpoint_id, days_back)


@router.get("/api/ack-distribution")
def get_ack_dist(
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    session: Session = Depends(get_session)
):
    """Distribution des codes ACK."""
    return get_ack_distribution(session, scenario_id, endpoint_id, days_back)


@router.get("/api/timeline")
def get_timeline(
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    session: Session = Depends(get_session)
):
    """Timeline d'exécutions par jour."""
    return get_scenario_timeline(session, scenario_id, endpoint_id, days_back)


@router.get("/api/comparison")
def get_comparison(
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    limit: int = 10,
    session: Session = Depends(get_session)
):
    """Comparaison de performances entre scénarios."""
    return get_scenario_comparison(session, endpoint_id, days_back, limit)


@router.get("/api/run/{run_id}/errors")
def get_run_errors(
    run_id: int,
    session: Session = Depends(get_session)
):
    """Détail des erreurs pour un run spécifique."""
    return get_step_error_summary(session, run_id)


@router.get("/api/scenario/{scenario_id}/status")
def get_scenario_status_api(
    scenario_id: int,
    endpoint_id: Optional[int] = None,
    session: Session = Depends(get_session)
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
    session: Session = Depends(get_session)
):
    """Affiche l'état des scénarios pour chaque EJ avec filtrage des erreurs."""
    from app.models_structure import EntiteJuridique
    
    # Récupérer toutes les EJ
    ej_list = session.exec(
        select(EntiteJuridique).order_by(EntiteJuridique.name)
    ).all()
    
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
        stats["error_scenarios"] = len([s for s in scenarios if s.has_errors and not s.is_partial])
    
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
    return get_templates_with_filters(request).TemplateResponse(request, "scenarios/ej_scenarios_status.html", ctx)


@router.get("/api/ej/{ej_id}/scenarios-status")
def get_ej_scenarios_status(
    ej_id: int,
    only_failed: bool = False,
    session: Session = Depends(get_session)
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
        ]
    }
