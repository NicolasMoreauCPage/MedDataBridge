"""Reclasse les scénarios SIU existants hors de la famille IHE PAM.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/reclassify_hl7_siu_scenarios.py
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.db import engine
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_protocol_classifier import classify_hl7_scenario
from app.services.scenario_qualification_service import assign_theme, ensure_theme


def main() -> None:
    with Session(engine) as session:
        steps_by_scenario: dict[int, list[InteropScenarioStep]] = {}
        for step in session.exec(select(InteropScenarioStep)).all():
            steps_by_scenario.setdefault(step.scenario_id, []).append(step)

        ensure_theme(session, "hl7", "HL7 v2")
        siu_theme = ensure_theme(session, "hl7.siu", "Rendez-vous (SIU)", parent_key="hl7")
        mixed_theme = ensure_theme(session, "hl7.mixte", "Mouvements et rendez-vous", parent_key="hl7")
        changed = pure = mixed = 0
        now = datetime.utcnow()

        for scenario in session.exec(select(InteropScenario)).all():
            family = classify_hl7_scenario(steps_by_scenario.get(scenario.id, []))
            if not family:
                continue
            category = "HL7_SIU" if family == "siu" else "HL7_MIXTE"
            theme = siu_theme if family == "siu" else mixed_theme
            if scenario.category != category or scenario.protocol != "HL7" or scenario.legacy_package != theme.key:
                scenario.category, scenario.protocol = category, "HL7"
                scenario.legacy_package, scenario.updated_at = theme.key, now
                session.add(scenario)
                changed += 1
            assign_theme(session, scenario.id, theme.id, primary=True)
            pure += family == "siu"
            mixed += family == "mixed_siu"

            review = session.exec(
                select(ScenarioCatalogReview).where(ScenarioCatalogReview.scenario_id == scenario.id)
            ).first()
            if review and review.status == "repairable":
                review.note = "Réparable : scénario HL7 v2 SIU de rendez-vous, hors périmètre IHE PAM."
                review.reviewed_at = now
                session.add(review)

        session.commit()
    print(f"Scénarios SIU purs : {pure}; mixtes ADT/SIU : {mixed}; reclassés : {changed}.")


if __name__ == "__main__":
    main()
