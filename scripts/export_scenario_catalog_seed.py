#!/usr/bin/env python3
"""Fige le catalogue de qualification dans une ressource rejouable par Alembic.

Le script est volontairement explicite : il exporte le catalogue administré
après qualification, pas les journaux d'exécution ni les données cliniques.
Il sert à préparer une nouvelle migration de données de référence.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.db import engine
from app.models_qualification import ScenarioTheme, ScenarioThemeAssignment
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep


DEFAULT_OUTPUT = Path("data/scenario_catalog_seed_20260912.json")


def _value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _record(item: Any, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    return {
        key: _value(value)
        for key, value in item.model_dump().items()
        if key not in excluded
    }


def export_catalog(output: Path) -> dict[str, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        scenarios = session.exec(select(InteropScenario).order_by(InteropScenario.key)).all()
        scenario_by_id = {item.id: item for item in scenarios}
        themes = session.exec(select(ScenarioTheme).order_by(ScenarioTheme.key)).all()
        theme_by_id = {item.id: item for item in themes}
        payload = {
            "schema_version": 1,
            "generated_at": datetime.utcnow().isoformat(),
            # Le catalogue livré ne doit jamais embarquer un contexte GHT local
            # ni un lien de version SQL. Ces références ne sont pas portables
            # sur une installation neuve.
            "scenarios": [
                _record(item, {"id", "current_version_id", "ght_context_id"})
                for item in scenarios
            ],
            "steps": [
                {**_record(item, {"id", "scenario_id"}), "scenario_key": scenario_by_id[item.scenario_id].key}
                for item in session.exec(select(InteropScenarioStep).order_by(InteropScenarioStep.scenario_id, InteropScenarioStep.order_index, InteropScenarioStep.id)).all()
                if item.scenario_id in scenario_by_id
            ],
            "reviews": [
                {**_record(item, {"id", "scenario_id"}), "scenario_key": scenario_by_id[item.scenario_id].key}
                for item in session.exec(select(ScenarioCatalogReview).order_by(ScenarioCatalogReview.scenario_id)).all()
                if item.scenario_id in scenario_by_id
            ],
            "themes": [_record(item, {"id", "parent_id"}) | {"parent_key": theme_by_id[item.parent_id].key if item.parent_id in theme_by_id else None} for item in themes],
            "theme_assignments": [
                {
                    "scenario_key": scenario_by_id[item.scenario_id].key,
                    "theme_key": theme_by_id[item.theme_id].key,
                    "is_primary": item.is_primary,
                    "created_at": _value(item.created_at),
                }
                for item in session.exec(select(ScenarioThemeAssignment)).all()
                if item.scenario_id in scenario_by_id and item.theme_id in theme_by_id
            ],
        }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: len(value) for key, value in payload.items() if isinstance(value, list)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    counts = export_catalog(args.output)
    print(", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
