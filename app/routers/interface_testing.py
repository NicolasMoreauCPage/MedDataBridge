"""Points d'entrée légers pour superviser les tests d'interfaces."""
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db import get_session
from app.models_endpoints import SystemEndpoint
from app.models_qualification import (
    QualificationCampaign,
    QualificationCampaignItem,
    QualificationCampaignRun,
)
from app.models_scenario_runs import ScenarioExecutionRun
from app.models_scenarios import InteropScenario
from app.services.interface_metrics import interface_metrics_service
from app.services.qualification_engine import run_campaign, run_qualification

router = APIRouter(prefix="/interface-testing", tags=["Interface Testing"])
ui_router = APIRouter(prefix="/ui/interface-testing", tags=["Interface Testing UI"])


class QualificationRunRequest(BaseModel):
    scenario_id: int
    endpoint_id: int
    dry_run: bool = True


class CampaignItemRequest(BaseModel):
    scenario_id: int
    endpoint_id: int
    order_index: int = 0
    is_active: bool = True


class CampaignCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    profile: str = Field(default="IHE_PAM_FR", max_length=120)
    items: list[CampaignItemRequest] = Field(default_factory=list)


def _decode_evidence(raw: Optional[str]):
    if not raw:
        return None
    try:
        import json

        return json.loads(raw)
    except ValueError:
        return raw


def _run_response(run: ScenarioExecutionRun) -> dict:
    return {
        "id": run.id,
        "scenario_id": run.scenario_id,
        "endpoint_id": run.endpoint_id,
        "status": run.status,
        "qualification_verdict": run.qualification_verdict,
        "assertion_total": run.assertion_total,
        "assertion_passed": run.assertion_passed,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "evidence": _decode_evidence(run.evidence_json),
    }


@router.get("")
async def interface_testing_home() -> dict:
    """Décrit les outils disponibles sans simuler une exécution distante."""
    return {
        "status": "ready",
        "scenario_generator": "/test-scenario-generator/generate",
        "metrics": "/interface-testing/metrics",
        "qualification_run": "/interface-testing/qualification/runs",
        "campaigns": "/interface-testing/qualification/campaigns",
        "note": "La génération est locale ; l'envoi utilise les endpoints configurés.",
    }


@router.get("/metrics")
async def interface_testing_metrics() -> dict:
    """Retourne les métriques agrégées des interfaces instrumentées."""
    metrics = interface_metrics_service.get_interface_metrics()
    return jsonable_encoder(asdict(metrics))


@router.post("/qualification/runs")
async def start_qualification_run(
    payload: QualificationRunRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Lance une qualification traçable d'un scénario sur un endpoint.

    ``dry_run`` vaut vrai par défaut : il permet de valider le jeu de tests et
    ses critères sans émettre de message vers le partenaire.
    """
    scenario = session.get(InteropScenario, payload.scenario_id)
    endpoint = session.get(SystemEndpoint, payload.endpoint_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scénario introuvable")
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint introuvable")
    try:
        result = await run_qualification(session, scenario, endpoint, dry_run=payload.dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    run = session.get(ScenarioExecutionRun, result["run_id"])
    return jsonable_encoder(_run_response(run)) if run else jsonable_encoder(result)


@router.get("/qualification/runs/{run_id}")
async def qualification_run_detail(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(ScenarioExecutionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Exécution introuvable")
    return jsonable_encoder(_run_response(run))


@router.post("/qualification/campaigns")
def create_qualification_campaign(
    payload: CampaignCreateRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Crée une campagne ordonnée de scénarios/endpoints."""
    if session.exec(select(QualificationCampaign).where(QualificationCampaign.key == payload.key)).first():
        raise HTTPException(status_code=409, detail="Cette clé de campagne existe déjà")
    for item in payload.items:
        if not session.get(InteropScenario, item.scenario_id):
            raise HTTPException(status_code=404, detail=f"Scénario {item.scenario_id} introuvable")
        if not session.get(SystemEndpoint, item.endpoint_id):
            raise HTTPException(status_code=404, detail=f"Endpoint {item.endpoint_id} introuvable")

    campaign = QualificationCampaign(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        profile=payload.profile,
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    for item in payload.items:
        session.add(
            QualificationCampaignItem(
                campaign_id=campaign.id,
                scenario_id=item.scenario_id,
                endpoint_id=item.endpoint_id,
                order_index=item.order_index,
                is_active=item.is_active,
            )
        )
    session.commit()
    return jsonable_encoder({"id": campaign.id, "key": campaign.key, "items": len(payload.items)})


@router.post("/qualification/campaigns/{campaign_id}/runs")
async def start_campaign_run(
    campaign_id: int,
    dry_run: bool = True,
    session: Session = Depends(get_session),
) -> dict:
    campaign = session.get(QualificationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")
    if not campaign.is_active:
        raise HTTPException(status_code=409, detail="Campagne désactivée")
    campaign_run = await run_campaign(session, campaign, dry_run=dry_run)
    return jsonable_encoder(
        {
            "id": campaign_run.id,
            "campaign_id": campaign_run.campaign_id,
            "status": campaign_run.status,
            "total_items": campaign_run.total_items,
            "passed_items": campaign_run.passed_items,
            "failed_items": campaign_run.failed_items,
            "evidence": _decode_evidence(campaign_run.evidence_json),
        }
    )


@router.get("/qualification/campaign-runs/{campaign_run_id}")
async def campaign_run_detail(campaign_run_id: int, session: Session = Depends(get_session)) -> dict:
    campaign_run = session.get(QualificationCampaignRun, campaign_run_id)
    if not campaign_run:
        raise HTTPException(status_code=404, detail="Exécution de campagne introuvable")
    return jsonable_encoder(
        {
            "id": campaign_run.id,
            "campaign_id": campaign_run.campaign_id,
            "status": campaign_run.status,
            "total_items": campaign_run.total_items,
            "passed_items": campaign_run.passed_items,
            "failed_items": campaign_run.failed_items,
            "started_at": campaign_run.started_at,
            "finished_at": campaign_run.finished_at,
            "evidence": _decode_evidence(campaign_run.evidence_json),
        }
    )


@ui_router.get("")
async def interface_testing_ui() -> RedirectResponse:
    """Point d'entrée UI conservé pour les anciens liens du menu."""
    return RedirectResponse(url="/ui/test-scenarios", status_code=303)
