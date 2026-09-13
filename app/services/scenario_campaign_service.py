"""Campagnes de scénarios fondées sur les jeux et l'outbox durables."""

from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.models_qualification import QualificationCampaign, QualificationCampaignItem, QualificationCampaignRun
from app.models_endpoints import SystemEndpoint
from app.models_scenarios import InteropScenario
from app.models_scenario_runs import ScenarioPlay
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


def queue_scenario_campaign(session: Session, campaign: QualificationCampaign, *, dry_run: bool = False) -> QualificationCampaignRun:
    """Enregistre une campagne avant toute émission.

    La persistance précède l'exécution afin qu'un redémarrage ne fasse jamais
    disparaître la demande de qualification.
    """
    total = len(session.exec(
        select(QualificationCampaignItem)
        .where(QualificationCampaignItem.campaign_id == campaign.id)
        .where(QualificationCampaignItem.is_active == True)  # noqa: E712
    ).all())
    run = QualificationCampaignRun(
        campaign_id=campaign.id,
        status="queued",
        dry_run=dry_run,
        total_items=total,
        evidence_json="[]",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _evidence(run: QualificationCampaignRun) -> list[dict]:
    try:
        value = json.loads(run.evidence_json or "[]")
    except json.JSONDecodeError:
        value = []
    return value if isinstance(value, list) else []


def _existing_play(session: Session, run: QualificationCampaignRun, item: QualificationCampaignItem) -> ScenarioPlay | None:
    """Retrouve un jeu déjà créé si le processus s'est arrêté entre deux commits."""
    for play in session.exec(select(ScenarioPlay).where(ScenarioPlay.scenario_id == item.scenario_id)).all():
        try:
            options = json.loads(play.options_json or "{}")
        except json.JSONDecodeError:
            continue
        if options.get("campaign_run_id") == run.id and options.get("campaign_item_id") == item.id:
            return play
    return None


async def process_scenario_campaign(
    session: Session,
    run_id: int,
    *,
    max_items: int = 1,
) -> QualificationCampaignRun:
    """Exécute un petit nombre d'éléments et conserve la progression.

    Le planificateur appelle cette fonction périodiquement. Chaque jeu porte
    l'identifiant de la campagne et de son item ; une reprise retrouve donc le
    jeu déjà préparé au lieu de générer de nouveaux identifiants.
    """
    run = session.get(QualificationCampaignRun, run_id)
    if not run:
        raise ValueError("Exécution de campagne introuvable")
    if run.status in {"passed", "failed", "error"}:
        return run
    campaign = session.get(QualificationCampaign, run.campaign_id)
    if not campaign or not campaign.is_active:
        run.status, run.error_message, run.finished_at = "error", "Campagne introuvable ou désactivée", datetime.utcnow()
        run.updated_at = datetime.utcnow()
        session.add(run)
        session.commit()
        return run
    items = session.exec(
        select(QualificationCampaignItem)
        .where(QualificationCampaignItem.campaign_id == campaign.id)
        .where(QualificationCampaignItem.is_active == True)  # noqa: E712
        .order_by(QualificationCampaignItem.order_index, QualificationCampaignItem.id)
    ).all()
    if run.status == "queued":
        run.status, run.started_at, run.updated_at = "running", datetime.utcnow(), datetime.utcnow()
    evidence = _evidence(run)
    completed = {entry.get("item_id") for entry in evidence}
    processed = 0
    for item in items[run.next_item_index:]:
        if processed >= max_items:
            break
        if item.id in completed:
            run.next_item_index += 1
            continue
        scenario, endpoint = session.get(InteropScenario, item.scenario_id), session.get(SystemEndpoint, item.endpoint_id)
        try:
            if not scenario or not endpoint:
                raise ScenarioPlayError("Scénario ou endpoint introuvable")
            play = _existing_play(session, run, item)
            if play is None:
                play = prepare_scenario_play(session, scenario, [endpoint], dry_run=run.dry_run)
                play.options_json = json.dumps({"campaign_run_id": run.id, "campaign_item_id": item.id})
                session.add(play)
                session.commit()
            if play.status not in {"success", "dry_run", "error", "partial"}:
                play = await execute_scenario_play(session, play.id)
            if play.status == "scheduled":
                # Ne pas consommer l'item tant que ses délais/retries durables
                # ne sont pas terminés. Le prochain passage retrouve ce jeu
                # via ``_existing_play`` et conserve ses identifiants.
                run.status, run.updated_at = "running", datetime.utcnow()
                session.add(run)
                session.commit()
                session.refresh(run)
                return run
            passed = play.status in {"success", "dry_run"}
            entry = {"item_id": item.id, "campaign_item_id": item.id, "play_id": play.id, "play_key": play.play_key, "status": play.status, "verdict": "passed" if passed else "failed"}
        except Exception as exc:  # one bad test must not discard a campaign
            entry = {"item_id": item.id, "verdict": "failed", "error": str(exc)[:1000]}
        evidence.append(entry)
        completed.add(item.id)
        run.next_item_index += 1
        run.passed_items = sum(row.get("verdict") == "passed" for row in evidence)
        run.failed_items = len(evidence) - run.passed_items
        run.evidence_json, run.updated_at = json.dumps(evidence, ensure_ascii=False), datetime.utcnow()
        session.add(run)
        session.commit()
        processed += 1
    if run.next_item_index >= len(items):
        run.status = "passed" if run.failed_items == 0 else "failed"
        run.finished_at, run.updated_at = datetime.utcnow(), datetime.utcnow()
        session.add(run)
        session.commit()
    session.refresh(run)
    return run


async def process_queued_campaigns(session: Session, *, limit: int = 5) -> dict[str, int]:
    """Fait progresser plusieurs campagnes sans monopoliser le serveur."""
    runs = session.exec(
        select(QualificationCampaignRun)
        .where(QualificationCampaignRun.status.in_(["queued", "running"]))
        .order_by(QualificationCampaignRun.started_at, QualificationCampaignRun.id)
        .limit(limit)
    ).all()
    result = {"processed": 0, "completed": 0}
    for run in runs:
        updated = await process_scenario_campaign(session, run.id, max_items=1)
        result["processed"] += 1
        result["completed"] += int(updated.status in {"passed", "failed", "error"})
    return result
