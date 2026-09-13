"""Installation idempotente du catalogue de qualification versionné.

Cette ressource est appelée depuis la migration Alembic et lors du bootstrap
d'une base vide. Elle n'écrase jamais un scénario, une revue ou un thème local
déjà présent : le catalogue livré reste donc une donnée de référence, pas une
restauration destructive.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Connection
from sqlmodel import Session, select

from app.models_qualification import ScenarioTheme, ScenarioThemeAssignment
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep


SEED_MARKER = "catalog-seed-20260912"
SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "scenario_catalog_seed_20260912.json"
_DATE_FIELDS = {"created_at", "updated_at", "reviewed_at"}


def _read() -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise ValueError("Version de catalogue de scénarios non prise en charge")
    return raw


def _datetime_values(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: datetime.fromisoformat(value) if key in _DATE_FIELDS and isinstance(value, str) else value
        for key, value in item.items()
    }


def _tags(value: str | None) -> str:
    tags = [tag.strip() for tag in (value or "").split(",") if tag.strip()]
    if SEED_MARKER not in tags:
        tags.append(SEED_MARKER)
    return ",".join(tags)


def apply_catalog_seed(bind: Connection) -> dict[str, int]:
    """Ajoute les lignes de référence absentes et retourne le nombre créé."""
    raw = _read()
    created = {"scenarios": 0, "steps": 0, "reviews": 0, "themes": 0, "assignments": 0}
    # Certaines très anciennes installations étaient marquées à une révision
    # antérieure tout en ne possédant qu'une table de scénarios minimale. Ne
    # jamais laisser le seed de données empêcher leur mise à niveau : les
    # migrations suivantes complètent le schéma et l'administrateur pourra
    # ensuite importer le catalogue. Les bases normales possèdent toujours la
    # clé métier avant cette révision.
    scenario_columns = {
        column["name"] for column in bind.dialect.get_columns(bind, "interopscenario")
    }
    if "key" not in scenario_columns:
        return created
    with Session(bind=bind) as session:
        themes = {item.key: item for item in session.exec(select(ScenarioTheme)).all()}
        # Les parents sont créés avant leurs enfants, quelle que soit l'ordre
        # matériel du fichier JSON.
        pending = list(raw["themes"])
        while pending:
            next_pending: list[dict[str, Any]] = []
            progressed = False
            for item in pending:
                if item["key"] in themes:
                    continue
                parent_key = item.get("parent_key")
                if parent_key and parent_key not in themes:
                    next_pending.append(item)
                    continue
                values = _datetime_values({key: value for key, value in item.items() if key != "parent_key"})
                values["parent_id"] = themes[parent_key].id if parent_key else None
                theme = ScenarioTheme(**values)
                session.add(theme)
                session.flush()
                themes[theme.key] = theme
                created["themes"] += 1
                progressed = True
            if not next_pending:
                break
            if not progressed:
                raise ValueError("Hiérarchie de thèmes de scénario invalide")
            pending = next_pending

        scenarios = {item.key: item for item in session.exec(select(InteropScenario)).all()}
        for item in raw["scenarios"]:
            if item["key"] in scenarios:
                continue
            values = _datetime_values(item)
            # Compatibilité avec un éventuel export de catalogue plus ancien :
            # le seed reste global et ne doit pas référencer un GHT source.
            values.pop("ght_context_id", None)
            values.pop("current_version_id", None)
            values["tags"] = _tags(values.get("tags"))
            scenario = InteropScenario(**values)
            session.add(scenario)
            session.flush()
            scenarios[scenario.key] = scenario
            created["scenarios"] += 1

        steps_by_scenario: dict[int, set[tuple[int, str]]] = {}
        for step in session.exec(select(InteropScenarioStep)).all():
            steps_by_scenario.setdefault(step.scenario_id, set()).add((step.order_index, step.payload))
        for item in raw["steps"]:
            scenario = scenarios.get(item["scenario_key"])
            if scenario is None:
                continue
            values = _datetime_values({key: value for key, value in item.items() if key != "scenario_key"})
            signature = (values["order_index"], values["payload"])
            known = steps_by_scenario.setdefault(scenario.id, set())
            if signature in known:
                continue
            session.add(InteropScenarioStep(scenario_id=scenario.id, **values))
            known.add(signature)
            created["steps"] += 1

        reviewed = {item.scenario_id for item in session.exec(select(ScenarioCatalogReview)).all()}
        for item in raw["reviews"]:
            scenario = scenarios.get(item["scenario_key"])
            if scenario is None or scenario.id in reviewed:
                continue
            values = _datetime_values({key: value for key, value in item.items() if key != "scenario_key"})
            session.add(ScenarioCatalogReview(scenario_id=scenario.id, **values))
            reviewed.add(scenario.id)
            created["reviews"] += 1

        assigned = {
            (item.scenario_id, item.theme_id)
            for item in session.exec(select(ScenarioThemeAssignment)).all()
        }
        for item in raw["theme_assignments"]:
            scenario, theme = scenarios.get(item["scenario_key"]), themes.get(item["theme_key"])
            if scenario is None or theme is None or (scenario.id, theme.id) in assigned:
                continue
            session.add(ScenarioThemeAssignment(
                scenario_id=scenario.id,
                theme_id=theme.id,
                is_primary=bool(item.get("is_primary", True)),
                created_at=datetime.fromisoformat(item["created_at"]),
            ))
            assigned.add((scenario.id, theme.id))
            created["assignments"] += 1
        # La transaction est possédée par Alembic (ou par l'appelant) : ne pas
        # la valider ici afin que schéma et données restent atomiques.
        session.flush()
    return created
