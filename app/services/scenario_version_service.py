"""Versionnement immuable des scénarios de qualification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlmodel import Session, select

from app.models.scenarios import InteropScenario, ScenarioVersion


def scenario_snapshot(scenario: InteropScenario) -> dict:
    """Représentation canonique, exportable et indépendante de la base."""
    return {
        "key": scenario.key,
        "name": scenario.name,
        "description": scenario.description,
        "functional_comment": scenario.functional_comment,
        "category": scenario.category,
        "protocol": scenario.protocol,
        "preconditions_json": scenario.preconditions_json,
        "assertions_json": scenario.assertions_json,
        "expected_outcome_json": scenario.expected_outcome_json,
        "tags": scenario.tags,
        "steps": [
            {
                "order_index": step.order_index, "name": step.name, "description": step.description,
                "message_format": step.message_format, "message_type": step.message_type,
                "payload": step.payload, "delay_seconds": step.delay_seconds,
                "assertions_json": step.assertions_json,
            }
            for step in sorted(scenario.steps or [], key=lambda item: (item.order_index, item.id or 0))
        ],
    }


def snapshot_scenario_version(session: Session, scenario: InteropScenario, *, comment: str | None = None, publish: bool = False) -> ScenarioVersion:
    content = scenario_snapshot(scenario)
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    latest = session.exec(
        select(ScenarioVersion)
        .where(ScenarioVersion.scenario_id == scenario.id)
        .order_by(ScenarioVersion.version_number.desc())
    ).first()
    if latest and latest.content_checksum == checksum:
        if publish and latest.status != "published":
            latest.status, latest.published_at = "published", datetime.utcnow()
            scenario.current_version_id, scenario.version = latest.id, latest.version_number
            session.add_all([latest, scenario])
        return latest
    version = ScenarioVersion(
        scenario_id=scenario.id,
        version_number=(latest.version_number if latest else 0) + 1,
        status="published" if publish else "draft",
        content_json=raw,
        content_checksum=checksum,
        comment=comment,
        published_at=datetime.utcnow() if publish else None,
    )
    session.add(version)
    session.flush()
    if publish:
        for existing in session.exec(
            select(ScenarioVersion)
            .where(ScenarioVersion.scenario_id == scenario.id)
            .where(ScenarioVersion.status == "published")
            .where(ScenarioVersion.id != version.id)
        ).all():
            existing.status = "archived"
            session.add(existing)
        scenario.current_version_id, scenario.version = version.id, version.version_number
        session.add(scenario)
    return version


def current_scenario_version(session: Session, scenario: InteropScenario) -> ScenarioVersion:
    if scenario.current_version_id:
        current = session.get(ScenarioVersion, scenario.current_version_id)
        if current:
            return current
    version = snapshot_scenario_version(session, scenario, publish=True)
    session.commit()
    session.refresh(version)
    return version
