"""Campagnes de scénarios fondées sur les jeux et l'outbox durables."""

from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.models_qualification import QualificationCampaign, QualificationCampaignItem, QualificationCampaignRun
from app.models_endpoints import SystemEndpoint
from app.models_scenarios import InteropScenario
from app.services.scenario_play_service import ScenarioPlayError, execute_scenario_play, prepare_scenario_play


async def run_scenario_campaign(session: Session, campaign: QualificationCampaign, *, dry_run: bool = False) -> QualificationCampaignRun:
    items = session.exec(
        select(QualificationCampaignItem)
        .where(QualificationCampaignItem.campaign_id == campaign.id)
        .where(QualificationCampaignItem.is_active == True)  # noqa: E712
        .order_by(QualificationCampaignItem.order_index, QualificationCampaignItem.id)
    ).all()
    run = QualificationCampaignRun(campaign_id=campaign.id, total_items=len(items), status="running")
    session.add(run)
    session.commit()
    evidence = []
    for item in items:
        scenario, endpoint = session.get(InteropScenario, item.scenario_id), session.get(SystemEndpoint, item.endpoint_id)
        try:
            if not scenario or not endpoint:
                raise ScenarioPlayError("Scénario ou endpoint introuvable")
            play = prepare_scenario_play(session, scenario, [endpoint], dry_run=dry_run)
            play = await execute_scenario_play(session, play.id)
            passed = play.status in {"success", "dry_run"}
            evidence.append({"item_id": item.id, "play_id": play.id, "play_key": play.play_key, "status": play.status, "verdict": "passed" if passed else "failed"})
        except Exception as exc:  # campaign evidence must survive an individual failure
            evidence.append({"item_id": item.id, "verdict": "failed", "error": str(exc)[:1000]})
    run.passed_items = sum(item["verdict"] == "passed" for item in evidence)
    run.failed_items = len(evidence) - run.passed_items
    run.status = "passed" if run.failed_items == 0 else "failed"
    run.finished_at, run.evidence_json = datetime.utcnow(), json.dumps(evidence, ensure_ascii=False)
    session.add(run)
    session.commit()
    return run
