from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import Session, select

from app.db import get_session
from app.models_endpoints import SystemEndpoint
from app.models import Dossier
from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate, ScenarioVersion
from app.models_structure import EntiteJuridique, GHTContext
from app.services.scenario_runner import ScenarioExecutionError, get_scenario
from app.services.scenario_capture import capture_dossier_as_scenario
from app.services.scenario_import import (
    ScenarioImportError,
    import_scenario_from_json,
    split_embedded_messages_in_scenario,
    validate_scenario_json,
)
from app.services.scenario_dashboard import (
    get_scenario_stats,
    get_ack_distribution,
    get_scenario_timeline,
    get_step_error_summary,
    get_scenario_comparison
)
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog, ScenarioDelivery
from app.models_outbox import OutboundMessage
from app.models_qualification import QualificationCampaign, QualificationCampaignItem, QualificationCampaignRun, ScenarioTheme, ScenarioThemeAssignment
from app.models_scenario_review import ScenarioCatalogReview
from app.services.scenario_play_service import (
    ScenarioPlayError,
    execute_scenario_play,
    get_play_details,
    prepare_scenario_play,
    retry_failed_scenario_play,
    retry_scenario_delivery,
)
from app.services.legacy_scenario_catalog import import_legacy_catalog
from app.services.scenario_qualification_service import (
    assign_theme,
    list_target_states,
    preflight_issues,
    set_target_active,
    theme_tree,
)
from app.services.message_diff import semantic_diff
from app.services.scenario_version_service import snapshot_scenario_version
from app.services.scenario_campaign_service import queue_scenario_campaign
from app.services.scenario_status_service import (
    get_last_scenario_status,
    get_scenarios_status_for_ej,
    get_scenarios_with_status,
)
from app.utils.flash import flash
from app.services.scenario_realistic_timeplan import suggest_scenario_timing_update
from app.services.scenario_authoring import (
    AUTHORING_DRAFT,
    create_manual_draft,
    create_template_draft,
    duplicate_scenario_draft,
    mark_ready,
    unique_scenario_key,
    validate_authoring,
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
    return [item for item in value if isinstance(item, int)] if isinstance(value, list) else []

logger = logging.getLogger(__name__)

def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_class=HTMLResponse)
def list_scenarios(
    request: Request,
    filter_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session)
):
    """Liste les scénarios avec leur dernier statut d'exécution."""
    
    # Récupérer les scénarios avec statut
    scenarios_data = get_scenarios_with_status(session, filter_by_status=filter_status)
    
    page = max(int(page), 1)
    page_size = min(max(int(page_size), 25), 100)
    total_count = len(scenarios_data)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(page, total_pages)
    first_index = (page - 1) * page_size
    page_items = scenarios_data[first_index:first_index + page_size]

    rows = []
    for scenario, scenario_status in page_items:
        rows.append(
            {
                "cells": [
                    scenario_status.visual_indicator,
                    scenario.name,
                    scenario.protocol,
                    len(scenario.steps or []),
                    scenario_status.ack_code or "—",
                    scenario_status.last_run_at.strftime("%Y-%m-%d %H:%M") if scenario_status.last_run_at else "—",
                ],
                "detail_url": f"/scenarios/{scenario.id}",
                "id": scenario.id,
                "css_class": scenario_status.css_class,
            }
        )

    ctx = {
        "request": request,
        "title": "Scénarios d'interopérabilité",
        "breadcrumbs": [{"label": "Scénarios", "url": "/scenarios"}],
        "headers": ["", "Nom", "Protocole", "Étapes", "Dernier ACK", "Dernière exécution"],
        "rows": rows,
        "show_actions": True,
        "actions": [
            {"label": "Nouveau scénario", "url": "/scenarios/new", "type": "link", "icon": "plus"},
            {"label": "Qualification", "url": "/scenarios/qualification", "type": "link", "icon": "check-circle"},
            {"label": "Administration", "url": "/scenarios/admin", "type": "link", "icon": "settings"},
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
        "pagination": {
            "page": page,
            "page_size": page_size,
            "page_size_param": "page_size",
            "max_page_size": 100,
            "total_pages": total_pages,
            "total_count": total_count,
            "base_url": "/scenarios" + (
                "?" + urlencode({"filter_status": filter_status, "page_size": page_size})
                if filter_status else "?" + urlencode({"page_size": page_size})
            ),
        },
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
        # Un contenu importé est immédiatement exploitable, mais doit passer
        # par la même revue que les autres méthodes de création avant émission.
        scenario.is_active = False
        scenario.authoring_status = AUTHORING_DRAFT
        scenario.authoring_metadata_json = json.dumps({
            "source": "import",
            "created_at": datetime.utcnow().isoformat(),
        })
        session.add(scenario)
        session.commit()
        
        flash(
            request, 
            f"Scénario '{scenario.name}' importé avec succès ({len(scenario.steps)} étapes)",
            level="success"
        )
        return RedirectResponse(url=f"/scenarios/{scenario.id}/authoring", status_code=303)
        
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
    endpoints_query = (
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled.is_(True))
        .where(SystemEndpoint.role.in_(["sender", "both"]))
    )
    
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
def bulk_execute_scenarios(
    request: Request,
    endpoint_id: int = Form(...),
    scenario_ids: list[int] = Form(...),
    repeat_count: int = Form(1),
    session: Session = Depends(get_session)
):
    """Convertit un lancement en masse en campagne persistante reprise-safe."""
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint or not endpoint.is_enabled or (endpoint.role or "").lower() not in {"sender", "both"}:
        flash(request, "Endpoint expéditeur introuvable ou désactivé.", level="error")
        return RedirectResponse(url="/scenarios/bulk-execute", status_code=status.HTTP_303_SEE_OTHER)
    selected = [
        scenario_id for scenario_id in dict.fromkeys(scenario_ids)
        if (scenario := session.get(InteropScenario, scenario_id)) and scenario.is_active
    ]
    if not selected:
        flash(request, "Aucun scénario actif sélectionné.", level="warning")
        return RedirectResponse(url="/scenarios/bulk-execute", status_code=status.HTTP_303_SEE_OTHER)
    repeat_count = min(max(int(repeat_count or 1), 1), 1000)
    key = f"bulk-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    campaign = QualificationCampaign(
        key=key,
        name=f"Exécution en masse du {datetime.utcnow():%d/%m/%Y %H:%M}",
        description=f"{len(selected)} scénario(s) × {repeat_count} jeu(x) vers {endpoint.name}",
        target_system_key=endpoint.target_system_key or endpoint.name,
    )
    session.add(campaign)
    session.flush()
    order = 0
    for _repeat in range(repeat_count):
        for scenario_id in selected:
            session.add(QualificationCampaignItem(
                campaign_id=campaign.id,
                scenario_id=scenario_id,
                endpoint_id=endpoint.id,
                order_index=order,
            ))
            order += 1
    session.commit()
    run = queue_scenario_campaign(session, campaign)
    flash(
        request,
        f"Campagne #{run.id} mise en file : {run.total_items} jeu(x). Elle reprendra automatiquement après un redémarrage.",
        level="success",
    )
    return RedirectResponse(url="/scenarios/campaigns", status_code=status.HTTP_303_SEE_OTHER)


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


@router.get("/admin", response_class=HTMLResponse)
def scenarios_admin(
    request: Request,
    active: Optional[str] = None,
    review_status: Optional[str] = None,
    category: Optional[str] = None,
    query: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Administration de tout le catalogue, y compris les scénarios désactivés."""
    scenarios = session.exec(select(InteropScenario).order_by(InteropScenario.name)).all()
    reviews = {
        review.scenario_id: review
        for review in session.exec(select(ScenarioCatalogReview)).all()
    }
    if active in {"active", "inactive"}:
        wanted = active == "active"
        scenarios = [item for item in scenarios if item.is_active == wanted]
    if review_status:
        scenarios = [
            item for item in scenarios
            if (reviews.get(item.id).status if reviews.get(item.id) else "unassessed") == review_status
        ]
    if category:
        scenarios = [item for item in scenarios if (item.category or "") == category]
    if query and query.strip():
        needle = query.strip().lower()
        scenarios = [
            item for item in scenarios
            if needle in " ".join(filter(None, [item.key, item.name, item.description, item.functional_comment, item.tags])).lower()
        ]
    review_labels = {
        "approved": "Conforme",
        "repairable": "Réparable",
        "manual_review": "À qualifier manuellement",
        "duplicate": "Doublon",
        "unassessed": "Non évalué",
    }
    all_scenarios = session.exec(select(InteropScenario)).all()
    review_counts = {
        status: sum(1 for item in all_scenarios if (reviews.get(item.id).status if reviews.get(item.id) else "unassessed") == status)
        for status in review_labels
    }
    categories = sorted({item.category for item in all_scenarios if item.category})
    return get_templates_with_filters(request).TemplateResponse(request, "scenarios_admin.html", {
        "request": request,
        "scenarios": scenarios,
        "reviews": reviews,
        "active": active or "",
        "review_status": review_status or "",
        "category": category or "",
        "query": query or "",
        "categories": categories,
        "review_counts": review_counts,
        "review_options": [{"value": key, "label": label} for key, label in review_labels.items()],
        "review_labels": review_labels,
    })


@router.post("/{scenario_id}/admin/toggle")
def toggle_scenario_catalog_active(
    scenario_id: int,
    request: Request,
    is_active: bool = Form(False),
    return_to: str = Form("admin"),
    session: Session = Depends(get_session),
):
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    scenario.is_active, scenario.updated_at = is_active, datetime.utcnow()
    session.add(scenario)
    session.commit()
    flash(request, f"Scénario {'activé' if is_active else 'désactivé'}.", level="success")
    destination = f"/scenarios/{scenario_id}" if return_to == "detail" else "/scenarios/admin"
    return RedirectResponse(url=destination, status_code=303)


@router.post("/{scenario_id}/admin/edit")
def edit_scenario_catalog_metadata(
    scenario_id: int,
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    functional_comment: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    protocol: str = Form("HL7"),
    tags: Optional[str] = Form(None),
    is_active: bool = Form(False),
    session: Session = Depends(get_session),
):
    """Édite les métadonnées sans toucher à la clé stable ni aux étapes."""
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    scenario.name = name.strip() or scenario.name
    scenario.description = description or None
    scenario.functional_comment = functional_comment or None
    scenario.category = category or None
    scenario.protocol = protocol.strip().upper() or "HL7"
    scenario.tags = tags or None
    scenario.is_active = is_active
    scenario.updated_at = datetime.utcnow()
    session.add(scenario)
    session.commit()
    flash(request, "Scénario mis à jour.", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.get("/qualification", response_class=HTMLResponse)
def qualification_catalog(
    request: Request,
    target_system_key: Optional[str] = None,
    theme_id: Optional[int] = None,
    query: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Catalogue opérationnel : état par logiciel, classement et pré-contrôles."""
    scenarios = session.exec(select(InteropScenario).where(InteropScenario.is_active == True).order_by(InteropScenario.category, InteropScenario.name)).all()  # noqa: E712
    assignments = session.exec(select(ScenarioThemeAssignment)).all()
    assignment_by_scenario = {item.scenario_id: item.theme_id for item in assignments if item.is_primary}
    themes = {item.id: item for item in session.exec(select(ScenarioTheme)).all()}
    states = list_target_states(session, target_system_key)
    states_by_scenario = {item.scenario_id: item for item in states} if target_system_key else {}
    if theme_id:
        scenarios = [item for item in scenarios if assignment_by_scenario.get(item.id) == theme_id]
    if query:
        needle = query.lower().strip()
        scenarios = [item for item in scenarios if needle in " ".join(filter(None, [item.name, item.description, item.functional_comment, item.tags])).lower()]
    targets = sorted({item.target_system_key for item in list_target_states(session)} | {endpoint.target_system_key or endpoint.name for endpoint in session.exec(select(SystemEndpoint)).all()})
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_qualification_catalog.html", {
        "request": request, "scenarios": scenarios, "states_by_scenario": states_by_scenario,
        "assignment_by_scenario": assignment_by_scenario, "themes": themes, "theme_tree": theme_tree(session),
        "targets": targets, "target_system_key": target_system_key, "theme_id": theme_id, "query": query or "",
        "preflight": {item.id: preflight_issues(item) for item in scenarios},
    })


@router.post("/qualification/catalog/import")
def import_legacy_qualification_catalog(request: Request, session: Session = Depends(get_session)):
    from pathlib import Path
    from data.scenarios_hprim_seed import scenarios as hprim_scenarios
    pam_raw = json.loads(Path("data/all_scenarios_dump.json").read_text(encoding="utf-8"))
    pam_scenarios = pam_raw.get("scenarios", pam_raw) if isinstance(pam_raw, dict) else pam_raw
    report = import_legacy_catalog(session, pam_scenarios + hprim_scenarios)
    flash(request, f"Catalogue historique importé : {report['created']} créés, {report['updated']} mis à jour, {report['duplicates']} doublons regroupés.", level="success")
    return RedirectResponse(url="/scenarios/qualification", status_code=303)


@router.post("/{scenario_id}/qualification/target")
def toggle_scenario_target(
    scenario_id: int, request: Request, target_system_key: str = Form(...), is_active: bool = Form(False),
    session: Session = Depends(get_session),
):
    if not session.get(InteropScenario, scenario_id):
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    set_target_active(session, scenario_id, target_system_key, is_active)
    flash(request, "Activation de la cible enregistrée.", level="success")
    return RedirectResponse(url=f"/scenarios/qualification?target_system_key={target_system_key}", status_code=303)


@router.post("/{scenario_id}/qualification/metadata")
def update_scenario_qualification_metadata(
    scenario_id: int, request: Request, functional_comment: Optional[str] = Form(None), theme_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
):
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    scenario.functional_comment, scenario.updated_at = (functional_comment or None), datetime.utcnow()
    session.add(scenario)
    if theme_id:
        if not session.get(ScenarioTheme, theme_id):
            raise HTTPException(status_code=404, detail="Thème introuvable")
        assign_theme(session, scenario_id, theme_id)
    session.commit()
    flash(request, "Commentaire et classement enregistrés.", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.post("/{scenario_id}/qualification/assertions")
def update_scenario_assertions(
    scenario_id: int, request: Request, preconditions_json: Optional[str] = Form(None), assertions_json: Optional[str] = Form(None), expected_outcome_json: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Édite des critères déclaratifs sans exécuter de code arbitraire."""
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    try:
        for label, raw in (("préconditions", preconditions_json), ("assertions", assertions_json)):
            if raw and not isinstance(json.loads(raw), list):
                raise ValueError(f"Les {label} doivent être une liste JSON")
        if expected_outcome_json and not isinstance(json.loads(expected_outcome_json), dict):
            raise ValueError("Le résultat attendu doit être un objet JSON")
        # Centralise la validation métier du contrat pour éviter de découvrir
        # une faute de configuration seulement après émission.
        from app.services.qualification_engine import _expected_outcome
        _expected_outcome(expected_outcome_json)
    except (ValueError, json.JSONDecodeError) as exc:
        flash(request, f"Critères non enregistrés : {exc}", level="error")
        return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)
    scenario.preconditions_json, scenario.assertions_json = preconditions_json or None, assertions_json or None
    scenario.expected_outcome_json = expected_outcome_json or None
    scenario.updated_at = datetime.utcnow()
    session.add(scenario)
    session.commit()
    flash(request, "Critères de qualification enregistrés.", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.get("/campaigns", response_class=HTMLResponse)
def qualification_campaigns(request: Request, session: Session = Depends(get_session)):
    campaigns = session.exec(select(QualificationCampaign).order_by(QualificationCampaign.name)).all()
    endpoints = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled.is_(True))
        .where(SystemEndpoint.role.in_(["sender", "both"]))
        .order_by(SystemEndpoint.name)
    ).all()
    scenarios = session.exec(select(InteropScenario).where(InteropScenario.is_active.is_(True)).order_by(InteropScenario.name)).all()
    recent_runs = session.exec(
        select(QualificationCampaignRun).order_by(QualificationCampaignRun.started_at.desc()).limit(50)
    ).all()
    runs_by_campaign = {}
    for run in recent_runs:
        runs_by_campaign.setdefault(run.campaign_id, run)
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_campaigns.html", {"request": request, "campaigns": campaigns, "endpoints": endpoints, "scenarios": scenarios, "runs_by_campaign": runs_by_campaign})


@router.post("/campaigns")
def create_campaign(
    request: Request, key: str = Form(...), name: str = Form(...), description: Optional[str] = Form(None),
    endpoint_id: int = Form(...), scenario_ids: list[int] = Form(...), session: Session = Depends(get_session),
):
    if session.exec(select(QualificationCampaign).where(QualificationCampaign.key == key)).first():
        flash(request, "Cette clé de campagne existe déjà.", level="error")
        return RedirectResponse(url="/scenarios/campaigns", status_code=303)
    endpoint = session.get(SystemEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    campaign = QualificationCampaign(key=key, name=name, description=description or None, target_system_key=endpoint.target_system_key or endpoint.name)
    session.add(campaign)
    session.flush()
    for index, scenario_id in enumerate(dict.fromkeys(scenario_ids)):
        if session.get(InteropScenario, scenario_id):
            session.add(QualificationCampaignItem(campaign_id=campaign.id, scenario_id=scenario_id, endpoint_id=endpoint_id, order_index=index))
    session.commit()
    flash(request, "Campagne créée. Elle est exécutable depuis l'espace Qualification.", level="success")
    return RedirectResponse(url="/scenarios/campaigns", status_code=303)


@router.post("/campaigns/{campaign_id}/run")
async def run_durable_campaign(campaign_id: int, request: Request, dry_run: bool = Form(False), session: Session = Depends(get_session)):
    campaign = session.get(QualificationCampaign, campaign_id)
    if not campaign or not campaign.is_active:
        raise HTTPException(status_code=404, detail="Campagne introuvable ou désactivée")
    run = queue_scenario_campaign(session, campaign, dry_run=dry_run)
    flash(request, f"Campagne #{run.id} mise en file ({run.total_items} scénario(s)). Sa progression est reprise automatiquement.", level="success")
    return RedirectResponse(url="/scenarios/campaigns", status_code=303)


# Routes d'auteur de scénario (doivent être avant /{scenario_id}). Elles réutilisent
# les modèles et la matérialisation historiques, mais évitent de demander un payload
# brut ou une clé technique avant d'avoir défini le parcours métier.
@router.get("/new/key-availability")
def scenario_key_availability(
    key: Optional[str] = None,
    name: Optional[str] = None,
    session: Session = Depends(get_session),
):
    requested = (key or name or "").strip()
    suggestion = unique_scenario_key(session, requested, name or requested or "scenario")
    return {
        "requested_key": requested,
        "suggested_key": suggestion,
        "available": bool(requested) and suggestion == requested,
    }


@router.get("/new", response_class=HTMLResponse)
def new_scenario_form(request: Request, session: Session = Depends(get_session)):
    """Assistant unique : modèle, duplication, import ou mode expert."""
    templates = session.exec(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.is_active.is_(True))
        .order_by(ScenarioTemplate.category, ScenarioTemplate.name)
    ).all()
    source_scenarios = session.exec(
        select(InteropScenario)
        .where(InteropScenario.authoring_status != AUTHORING_DRAFT)
        .order_by(InteropScenario.name)
    ).all()
    ctx = {
        "request": request,
        "templates": templates,
        "source_scenarios": source_scenarios,
        "breadcrumbs": [
            {"label": "Scénarios", "url": "/scenarios"},
            {"label": "Nouveau scénario", "url": "/scenarios/new"},
        ],
    }
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_new.html", ctx)


@router.post("/new")
def create_scenario(
    request: Request,
    creation_mode: str = Form("manual"),
    key: Optional[str] = Form(None),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    protocol: str = Form("HL7"),
    tags: Optional[str] = Form(None),
    template_key: Optional[str] = Form(None),
    source_scenario_id: Optional[int] = Form(None),
    ipp_prefix: Optional[str] = Form(None),
    nda_prefix: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Crée un brouillon via le parcours choisi, puis ouvre sa revue guidée."""
    normalized_name = name.strip()
    if not normalized_name:
        flash(request, "Donnez un nom au scénario avant de continuer.", level="error")
        return RedirectResponse(url="/scenarios/new", status_code=303)
    try:
        if creation_mode == "template":
            template = session.exec(
                select(ScenarioTemplate).where(ScenarioTemplate.key == (template_key or ""))
            ).first()
            if not template or not template.is_active:
                raise ValueError("Choisissez un modèle de scénario disponible.")
            active_ej_id = getattr(getattr(request.state, "ej_context", None), "id", None)
            ej_context = session.get(EntiteJuridique, active_ej_id) if active_ej_id else None
            scenario = create_template_draft(
                session,
                template=template,
                name=normalized_name,
                description=description,
                category=category,
                requested_key=key,
                protocol="FHIR" if protocol == "FHIR" else "HL7v2",
                tags=tags,
                ej_context=ej_context,
                ipp_prefix=ipp_prefix,
                nda_prefix=nda_prefix,
            )
        elif creation_mode == "duplicate":
            source = session.get(InteropScenario, source_scenario_id)
            if not source:
                raise ValueError("Choisissez le scénario à dupliquer.")
            scenario = duplicate_scenario_draft(
                session,
                source=source,
                name=normalized_name,
                description=description,
                requested_key=key,
            )
        elif creation_mode == "manual":
            scenario = create_manual_draft(
                session,
                name=normalized_name,
                description=description,
                category=category,
                protocol=protocol,
                requested_key=key,
                tags=tags,
            )
        else:
            raise ValueError("Méthode de création inconnue.")
    except ValueError as exc:
        flash(request, str(exc), level="error")
        return RedirectResponse(url="/scenarios/new", status_code=303)

    flash(request, f"Brouillon « {scenario.name} » créé. Vérifiez-le avant de le rendre exécutable.", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario.id}/authoring", status_code=303)


@router.get("/{scenario_id}/authoring", response_class=HTMLResponse)
def scenario_authoring_review(scenario_id: int, request: Request, session: Session = Depends(get_session)):
    """Revue légère : chronologie, destinations proposées et validation de préparation."""
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
        step.id: sum(1 for endpoint in endpoints if (endpoint.kind or "").upper() in compatible_kinds.get(step.message_format.lower(), set()))
        for step in steps
    }
    issues = validate_authoring(session, scenario)
    return get_templates_with_filters(request).TemplateResponse(
        request,
        "scenario_authoring_review.html",
        {
            "request": request,
            "scenario": scenario,
            "steps": steps,
            "issues": [issue.as_dict() for issue in issues],
            "endpoint_counts": endpoint_counts,
            "breadcrumbs": [
                {"label": "Scénarios", "url": "/scenarios"},
                {"label": "Nouveau scénario", "url": "/scenarios/new"},
                {"label": "Revue", "url": f"/scenarios/{scenario.id}/authoring"},
            ],
        },
    )


@router.get("/{scenario_id}/authoring/preview")
def scenario_authoring_preview(scenario_id: int, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    issues = validate_authoring(session, scenario)
    return {
        "scenario": {
            "id": scenario.id,
            "name": scenario.name,
            "key": scenario.key,
            "status": scenario.authoring_status,
            "step_count": len(scenario.steps),
        },
        "valid": not any(issue.level == "error" for issue in issues),
        "issues": [issue.as_dict() for issue in issues],
        "steps": [
            {
                "id": step.id,
                "order_index": step.order_index,
                "name": step.name,
                "message_type": step.message_type,
                "message_format": step.message_format,
                "payload_preview": f"{step.payload[:240]}…" if len(step.payload) > 240 else step.payload,
            }
            for step in sorted(scenario.steps, key=lambda item: item.order_index)
        ],
    }


@router.post("/{scenario_id}/authoring/validate")
def validate_scenario_authoring(scenario_id: int, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    issues = validate_authoring(session, scenario)
    return {
        "valid": not any(issue.level == "error" for issue in issues),
        "issues": [issue.as_dict() for issue in issues],
    }


@router.post("/{scenario_id}/authoring/ready")
def ready_scenario_authoring(scenario_id: int, request: Request, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    issues = mark_ready(session, scenario)
    errors = [issue for issue in issues if issue.level == "error"]
    if errors:
        flash(request, errors[0].message, level="error")
        return RedirectResponse(url=f"/scenarios/{scenario.id}/authoring", status_code=303)
    flash(request, "Scénario prêt : il peut maintenant être exécuté ou complété en mode expert.", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario.id}", status_code=303)


@router.post("/{scenario_id}/steps")
def add_scenario_step(
    scenario_id: int,
    request: Request,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    message_format: str = Form("hl7"),
    message_type: Optional[str] = Form(None),
    payload: str = Form(""),
    delay_seconds: Optional[int] = Form(None),
    is_required: bool = Form(False),
    route_mode: str = Form("all_compatible"),
    route_endpoint_ids: list[int] = Form(default=[]),
    target_system_key: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Ajoute une étape à la fin d'un scénario existant (création manuelle pas-à-pas)."""
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")

    next_order = max([s.order_index for s in scenario.steps], default=0) + 1
    if route_mode not in {"all_compatible", "explicit", "target_system"}:
        raise HTTPException(status_code=400, detail="Mode de routage invalide")
    step = InteropScenarioStep(
        scenario_id=scenario_id,
        order_index=next_order,
        name=name or None,
        description=description or None,
        message_format=message_format,
        message_type=message_type or None,
        payload=payload,
        delay_seconds=delay_seconds,
        is_required=is_required,
        route_mode=route_mode,
        endpoint_ids_json=json.dumps(sorted(set(route_endpoint_ids))) if route_mode == "explicit" else None,
        target_system_key=(target_system_key or "").strip() or None,
    )
    session.add(step)
    session.commit()
    flash(request, f"Étape #{next_order} ajoutée au scénario", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.post("/{scenario_id}/steps/split-embedded")
def split_embedded_scenario_messages(
    scenario_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Sépare les messages historiques concaténés en étapes éditables."""
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    added = split_embedded_messages_in_scenario(session, scenario)
    if added:
        flash(request, f"{added} étape(s) créée(s) : un message par étape.", level="success")
    else:
        flash(request, "Aucun message concaténé à séparer.", level="info")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.post("/{scenario_id}/steps/{step_id}/delete")
def delete_scenario_step(
    scenario_id: int,
    step_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Supprime une étape d'un scénario (édition manuelle pas-à-pas)."""
    step = session.get(InteropScenarioStep, step_id)
    if not step or step.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Étape introuvable")

    session.delete(step)
    session.commit()
    flash(request, "Étape supprimée", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.post("/{scenario_id}/steps/{step_id}/edit")
def edit_scenario_step(
    scenario_id: int,
    step_id: int,
    request: Request,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    message_type: Optional[str] = Form(None),
    message_format: str = Form("hl7"),
    payload: str = Form(""),
    delay_seconds: Optional[int] = Form(None),
    is_required: bool = Form(False),
    route_mode: str = Form("all_compatible"),
    route_endpoint_ids: list[int] = Form(default=[]),
    target_system_key: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Modifie une étape sans changer le modèle source lors des futurs jeux."""
    step = session.get(InteropScenarioStep, step_id)
    if not step or step.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Étape introuvable")
    if route_mode not in {"all_compatible", "explicit", "target_system"}:
        raise HTTPException(status_code=400, detail="Mode de routage invalide")
    step.name, step.description = name or None, description or None
    step.message_type, step.message_format = message_type or None, message_format.lower().strip()
    step.payload, step.delay_seconds, step.updated_at = payload, delay_seconds, datetime.utcnow()
    step.is_required, step.route_mode = is_required, route_mode
    step.endpoint_ids_json = json.dumps(sorted(set(route_endpoint_ids))) if route_mode == "explicit" else None
    step.target_system_key = (target_system_key or "").strip() or None
    session.add(step)
    session.commit()
    flash(request, f"Étape #{step.order_index} mise à jour", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.post("/{scenario_id}/steps/{step_id}/move")
def move_scenario_step(
    scenario_id: int,
    step_id: int,
    request: Request,
    direction: str = Form(...),
    session: Session = Depends(get_session),
):
    """Échange une étape avec sa voisine tout en conservant un ordre dense."""
    step = session.get(InteropScenarioStep, step_id)
    if not step or step.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Étape introuvable")
    ordered = session.exec(
        select(InteropScenarioStep)
        .where(InteropScenarioStep.scenario_id == scenario_id)
        .order_by(InteropScenarioStep.order_index, InteropScenarioStep.id)
    ).all()
    index = next((i for i, item in enumerate(ordered) if item.id == step_id), None)
    target_index = index - 1 if direction == "up" else index + 1 if direction == "down" else None
    if index is None or target_index is None or not 0 <= target_index < len(ordered):
        return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)
    ordered[index], ordered[target_index] = ordered[target_index], ordered[index]
    # Values are rewritten in a second pass to tolerate pre-existing gaps.
    for position, item in enumerate(ordered, start=1):
        item.order_index, item.updated_at = position, datetime.utcnow()
        session.add(item)
    session.commit()
    flash(request, "Ordre des étapes mis à jour", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario_id}", status_code=303)


@router.get("/{scenario_id}", response_class=HTMLResponse)
def scenario_detail(scenario_id: int, request: Request, session: Session = Depends(get_session)):
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
        "themes": session.exec(select(ScenarioTheme).where(ScenarioTheme.is_active == True).order_by(ScenarioTheme.name)).all(),  # noqa: E712
        "current_theme_assignment": session.exec(
            select(ScenarioThemeAssignment).where(ScenarioThemeAssignment.scenario_id == scenario.id).where(ScenarioThemeAssignment.is_primary == True)  # noqa: E712
        ).first(),
        "preflight_issues": preflight_issues(scenario),
        "scenario_versions": session.exec(
            select(ScenarioVersion).where(ScenarioVersion.scenario_id == scenario.id).order_by(ScenarioVersion.version_number.desc())
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
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_detail.html", ctx)


@router.post("/{scenario_id}/versions/publish")
def publish_scenario_version(
    scenario_id: int, request: Request, comment: Optional[str] = Form(None), session: Session = Depends(get_session),
):
    scenario = session.get(InteropScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    version = snapshot_scenario_version(session, scenario, comment=comment or None, publish=True)
    session.commit()
    flash(request, f"Version {version.version_number} publiée et figée pour les prochains jeux.", level="success")
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
    flash(request, f"Scénario capturé depuis dossier {dossier.dossier_seq} (id={dossier.id})", level="success")
    return RedirectResponse(url=f"/scenarios/{scenario.id}", status_code=303)



@router.post("/{scenario_id}/send")
async def scenario_send(
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
        raise HTTPException(status_code=409, detail="Scénario désactivé : activez-le dans l’administration avant émission.")

    # ``endpoint_id`` stays accepted for bookmarked forms and the public API;
    # the UI now posts endpoint_ids and may select distinct MLLP/FHIR/HPRIM
    # endpoints in a single coherent play.
    selected_ids = list(dict.fromkeys(endpoint_ids + ([endpoint_id] if endpoint_id else [])))
    endpoints = [session.get(SystemEndpoint, selected_id) for selected_id in selected_ids]
    if not endpoints or any(endpoint is None for endpoint in endpoints):
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    endpoints = [endpoint for endpoint in endpoints if endpoint is not None]

    try:
        play = prepare_scenario_play(
            session, scenario, endpoints, dry_run=dry_run,
            step_id=step_id, start_order_index=start_order_index, error_policy=error_policy,
        )
        play = await execute_scenario_play(session, play.id)
        delivered = session.exec(
            select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)
        ).all()
        if play.status in {"success", "dry_run"}:
            flash(request, f"Jeu {play.play_key} {'prévisualisé' if dry_run else 'émis'} vers {len(endpoints)} endpoint(s) : {len(delivered)} livraison(s).", level="success")
        else:
            flash(request, f"Jeu {play.play_key} terminé avec le statut {play.status}. Consultez le détail des livraisons.", level="warning")
        return RedirectResponse(url=f"/scenarios/{scenario_id}/plays/{play.id}", status_code=303)
    except (ScenarioExecutionError, ScenarioPlayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{scenario_id}/plays/{play_id}", response_class=HTMLResponse)
def scenario_play_detail(scenario_id: int, play_id: int, request: Request, session: Session = Depends(get_session)):
    scenario = get_scenario(session, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    try:
        play, steps, deliveries = get_play_details(session, play_id)
    except ScenarioPlayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if play.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Jeu hors scénario")
    endpoints = {endpoint.id: endpoint for endpoint in session.exec(select(SystemEndpoint).where(SystemEndpoint.id.in_([row.endpoint_id for row in deliveries]))).all()}
    outbox_by_id = {row.id: row for row in session.exec(select(OutboundMessage).where(OutboundMessage.id.in_([delivery.outbox_id for delivery in deliveries if delivery.outbox_id]))).all()}
    return get_templates_with_filters(request).TemplateResponse(request, "scenario_play_detail.html", {
        "request": request, "scenario": scenario, "play": play, "steps": steps, "deliveries": deliveries,
        "endpoints_by_id": endpoints, "outbox_by_id": outbox_by_id, "identity": json.loads(play.identity_json or "{}"),
        "target_context_by_delivery": {
            item.id: json.loads(item.target_context_json or "{}") for item in deliveries
        },
        "validation_by_delivery": {
            item.id: json.loads(item.validation_json or "{}") for item in deliveries
        },
        "diffs_by_step": {
            item.id: semantic_diff(item.source_payload, item.compiled_payload, item.message_format)
            for item in steps
        },
        "breadcrumbs": [{"label": "Scénarios", "url": "/scenarios"}, {"label": scenario.name, "url": f"/scenarios/{scenario.id}"}, {"label": play.play_key, "url": ""}],
    })


@router.get("/{scenario_id}/plays/{play_id}/diagnostic.json")
def scenario_play_diagnostic(scenario_id: int, play_id: int, session: Session = Depends(get_session)):
    """Preuve portable : payloads, routage, réponses et tentatives d'un jeu."""
    play, steps, deliveries = get_play_details(session, play_id)
    if play.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Jeu hors scénario")
    outbox = {row.id: row for row in session.exec(select(OutboundMessage).where(OutboundMessage.id.in_([item.outbox_id for item in deliveries if item.outbox_id]))).all()}
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
async def scenario_delivery_retry(scenario_id: int, play_id: int, delivery_id: int, request: Request, session: Session = Depends(get_session)):
    """Technical retry: preserve the exact compiled payload and identifiers."""
    try:
        play, _, _ = get_play_details(session, play_id)
        if play.scenario_id != scenario_id:
            raise ScenarioPlayError("Jeu hors scénario")
        delivery = await retry_scenario_delivery(session, delivery_id)
    except ScenarioPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    flash(request, f"Livraison #{delivery.id} {'envoyée' if delivery.status == 'sent' else 'en erreur'} avec le même jeu.", level="success" if delivery.status == "sent" else "warning")
    return RedirectResponse(url=f"/scenarios/{scenario_id}/plays/{play_id}", status_code=303)


@router.post("/{scenario_id}/plays/{play_id}/retry-failed")
async def scenario_play_retry_failed(scenario_id: int, play_id: int, request: Request, session: Session = Depends(get_session)):
    """Reprend le reliquat d'un jeu sans jamais régénérer son identité."""
    try:
        play, _, _ = get_play_details(session, play_id)
        if play.scenario_id != scenario_id:
            raise ScenarioPlayError("Jeu hors scénario")
        play = await retry_failed_scenario_play(session, play_id)
    except ScenarioPlayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    level = "success" if play.status == "success" else "warning"
    flash(request, f"Reprise du jeu {play.play_key} terminée : {play.status}.", level=level)
    return RedirectResponse(url=f"/scenarios/{scenario_id}/plays/{play_id}", status_code=303)

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
