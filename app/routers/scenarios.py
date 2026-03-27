from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
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
from app.services.scenario_realistic_timeplan import suggest_scenario_timing_update
from app.services.scenario_identity_generator import generate_patient_identity

logger = logging.getLogger(__name__)

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
                "id": scenario.id,
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
            {"label": "Exécuter en masse", "url": "/scenarios/bulk-execute", "type": "link", "icon": "play"},
            {"label": "Importer", "url": "/scenarios/import", "type": "link", "icon": "upload"}
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
    # Provide endpoints for inline bulk execution (compact mode)
    endpoints = session.exec(select(SystemEndpoint).where(SystemEndpoint.is_enabled.is_(True)).order_by(SystemEndpoint.kind, SystemEndpoint.name)).all()
    ctx["all_endpoints"] = endpoints
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


@router.get("/bulk-execute", response_class=HTMLResponse)
def bulk_execute_scenarios_form(
    request: Request,
    filter_status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Formulaire pour exécuter plusieurs scénarios en masse sur un endpoint."""
    
    # Récupérer l'EJ sélectionnée dans le contexte
    ej_context = getattr(request.state, 'ej_context', None)
    ej_id = ej_context.id if ej_context else None
    
    # Récupérer tous les scénarios actifs avec leur statut
    scenarios_data = get_scenarios_with_status(session, filter_by_status=filter_status)
    
    # Construire la requête d'endpoints filtrés par EJ
    endpoints_query = select(SystemEndpoint).where(SystemEndpoint.is_enabled.is_(True))
    
    if ej_id:
        endpoints_query = endpoints_query.where(SystemEndpoint.entite_juridique_id == ej_id)
    
    all_endpoints = session.exec(endpoints_query.order_by(SystemEndpoint.kind, SystemEndpoint.name)).all()
    
    # Catégoriser les endpoints par rôle et type
    file_endpoints = [ep for ep in all_endpoints if ep.kind == "FILE"]
    fhir_endpoints = [ep for ep in all_endpoints if ep.kind == "FHIR"]
    mllp_endpoints = [ep for ep in all_endpoints if ep.kind == "MLLP"]
    other_endpoints = [ep for ep in all_endpoints if ep.kind not in ["FILE", "FHIR", "MLLP"]]
    
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "scenarios_bulk_execute_v2.html",
        {
            "scenarios": scenarios_data,
            "file_endpoints": file_endpoints,
            "fhir_endpoints": fhir_endpoints,
            "mllp_endpoints": mllp_endpoints,
            "other_endpoints": other_endpoints,
            "ej_name": ej_context.name if ej_context else "Non sélectionnée",
            "filter_status": filter_status,
            "filter_options": [
                {"label": "Tous les scénarios", "value": None},
                {"label": "✅ Succès (dernier run)", "value": "success"},
                {"label": "⚠️ Partiellement réussis", "value": "partial"},
                {"label": "❌ Erreurs (dernier run)", "value": "error"},
                {"label": "⏹️ Jamais exécutés", "value": "no_run"},
            ]
        }
    )


@router.post("/bulk-execute")
async def bulk_execute_scenarios(
    request: Request,
    endpoint_id: int = Form(...),
    scenario_ids: list[int] = Form(...),
    repeat_count: int = Form(1),
    session: Session = Depends(get_session)
):
    """Exécute plusieurs scénarios sur un endpoint en arrière-plan."""
    from app.services.scenario_runner import execute_scenario_on_endpoint
    from app.utils.flash import flash
    import asyncio
    
    # Vérifier que l'endpoint existe
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        flash(request, "error", "❌ Endpoint introuvable")
        return RedirectResponse(url="/scenarios/bulk-execute", status_code=status.HTTP_303_SEE_OTHER)
    
    if not scenario_ids or scenario_ids == ['']:
        flash(request, "warning", "⚠️ Aucun scénario sélectionné")
        return RedirectResponse(url="/scenarios/bulk-execute", status_code=status.HTTP_303_SEE_OTHER)
    
    # Convertir les scenario_ids en entiers et charger les noms avant de quitter la session
    scenario_ids_int = []
    scenario_names = {}
    total_messages_per_run = 0
    
    for scenario_id_str in scenario_ids:
        try:
            scenario_id = int(scenario_id_str)
            scenario_ids_int.append(scenario_id)
            
            scenario = session.get(InteropScenario, scenario_id)
            if scenario:
                scenario_names[scenario_id] = scenario.name
                steps = session.exec(
                    select(InteropScenarioStep)
                    .where(InteropScenarioStep.scenario_id == scenario_id)
                ).all()
                total_messages_per_run += len(steps)
        except (ValueError, TypeError):
            continue
    
    total_scenarios = len(scenario_ids_int)
    # Validate repeat_count
    try:
        repeat_count = int(repeat_count)
    except Exception:
        repeat_count = 1
    if repeat_count < 1:
        repeat_count = 1
    MAX_REPEAT = 1000
    if repeat_count > MAX_REPEAT:
        repeat_count = MAX_REPEAT

    total_messages = total_messages_per_run * repeat_count
    endpoint_name = endpoint.name
    endpoint_id_copy = endpoint.id
    
    # Fonction d'exécution en arrière-plan avec sa propre session
    async def run_scenarios_background():
        """Exécute les scénarios en arrière-plan avec une nouvelle session."""
        from app.db import session_factory
        
        success_count = 0
        error_count = 0
        failed_scenarios = []
        
        # Créer une nouvelle session pour la tâche de fond
        bg_session = session_factory()
        try:
            # Récupérer l'endpoint et les scénarios dans cette nouvelle session
            bg_endpoint = bg_session.get(SystemEndpoint, endpoint_id_copy)
            if not bg_endpoint:
                logger.error(f"[Background] Endpoint {endpoint_id_copy} introuvable")
                return
            
            # Exécuter chaque scénario 'repeat_count' fois
            for i in range(repeat_count):
                for scenario_id in scenario_ids_int:
                    scenario = bg_session.get(InteropScenario, scenario_id)
                    if not scenario:
                        error_count += 1
                        continue

                    scenario_name = scenario.name

                    # Charger les steps
                    steps = bg_session.exec(
                        select(InteropScenarioStep)
                        .where(InteropScenarioStep.scenario_id == scenario_id)
                        .order_by(InteropScenarioStep.order_index)
                    ).all()

                    if not steps:
                        error_count += 1
                        continue

                    try:
                        logger.info(f"[Background] Exécution ({i+1}/{repeat_count}) du scénario '{scenario_name}' sur '{endpoint_name}'")
                        result = await execute_scenario_on_endpoint(
                            endpoint=bg_endpoint,
                            scenario=scenario,
                            steps=steps,
                            session=bg_session
                        )

                        if result.get('error_count', 0) == 0:
                            success_count += 1
                            logger.info(f"[Background] ✅ '{scenario_name}' exécuté avec succès (run {i+1})")
                        else:
                            error_count += 1
                            failed_scenarios.append(scenario_name)
                            logger.warning(f"[Background] ⚠️ '{scenario_name}' exécuté avec {result.get('error_count', 0)} erreurs (run {i+1})")
                    except Exception as e:
                        error_count += 1
                        failed_scenarios.append(scenario_name)
                        logger.error(f"[Background] ❌ Erreur lors de l'exécution de '{scenario_name}': {str(e)[:200]}")
            
            # Log final
            if error_count == 0 and success_count > 0:
                logger.info(f"[Background] ✅ {success_count}/{total_scenarios} scénarios exécutés avec succès ({total_messages} messages)")
            elif success_count > 0:
                logger.warning(f"[Background] ⚠️ {success_count}/{total_scenarios} scénarios réussis, {error_count} en erreur")
            else:
                logger.error(f"[Background] ❌ Aucun scénario n'a pu être exécuté ({error_count} erreurs)")
        
        finally:
            bg_session.close()
    
    # Lancer l'exécution en arrière-plan sans attendre
    asyncio.create_task(run_scenarios_background())
    
    # Retourner immédiatement avec un message au user
    flash(request, "info", 
          f"⏱️ Exécution lancée en arrière-plan: {total_scenarios} scénario(s), {total_messages} message(s). "
          f"Vérifiez les logs ou revisitez cette page pour le statut final.")
    
    return RedirectResponse(url="/scenarios/bulk-execute", status_code=status.HTTP_303_SEE_OTHER)


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



# Dashboard route (must be before /{scenario_id} to avoid conflicts)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(request: Request):
    """Redirect /scenarios/dashboard to /scenarios/runs (the actual dashboard)."""
    return RedirectResponse(url="/scenarios/runs", status_code=302)


@router.get("/{scenario_id}", response_class=HTMLResponse)
def scenario_detail(scenario_id: int, request: Request, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")

    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled == True)
        .where(SystemEndpoint.role == "sender")
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
            log = await send_step(
                session,
                step,
                endpoint,
                identity_profile=generate_patient_identity(),
            )
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


@router.post("/{scenario_id}/suggest-realistic-timing")
def suggest_realistic_timing(
    scenario_id: int,
    session: Session = Depends(get_session)
):
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
        "suggested_config": {k: v for k, v in suggestion.items() if not k.startswith("_")},
        "analysis": {
            "detected_workflow": suggestion.get("_detected_workflow"),
            "workflow_description": suggestion.get("_workflow_description"),
            "event_sequence": suggestion.get("_event_sequence"),
        }
    }


@router.post("/{scenario_id}/apply-realistic-timing")
def apply_realistic_timing(
    scenario_id: int,
    session: Session = Depends(get_session)
):
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
        "message": f"Configuration temporelle réaliste appliquée avec succès (workflow: {suggestion.get('_detected_workflow')})"
    }
