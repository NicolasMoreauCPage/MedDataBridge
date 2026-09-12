"""Réordonne les scénarios PAM réparables lorsque la correction est certaine.

Sans ``--apply``, le script ne fait qu'afficher le diagnostic. Avec
``--apply``, seules les permutations mono-patient validées par l'automate PAM
sont enregistrées ; les autres restent à corriger manuellement.
"""

from __future__ import annotations

import sys
from datetime import datetime

from sqlmodel import Session, select

from app.db import engine
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_sequence_repair import apply_repaired_step_order


def main() -> None:
    apply = "--apply" in sys.argv[1:]
    with Session(engine) as session:
        reviews = {
            item.scenario_id: item
            for item in session.exec(select(ScenarioCatalogReview).where(ScenarioCatalogReview.status == "repairable")).all()
        }
        changed: list[tuple[int, str]] = []
        for scenario in session.exec(select(InteropScenario).where(InteropScenario.category == "IHE_PAM")).all():
            if scenario.id not in reviews:
                continue
            steps = session.exec(
                select(InteropScenarioStep)
                .where(InteropScenarioStep.scenario_id == scenario.id)
                .order_by(InteropScenarioStep.order_index, InteropScenarioStep.id)
            ).all()
            if apply_repaired_step_order(steps):
                changed.append((scenario.id, scenario.name))
                if apply:
                    scenario.updated_at = datetime.utcnow()
                    session.add(scenario)
                    for step in steps:
                        session.add(step)
        if apply:
            session.commit()
    print(f"{len(changed)} scénario(s) PAM réordonné(s){' et enregistré(s)' if apply else ' (simulation)' }.")
    for scenario_id, name in changed:
        print(f"- #{scenario_id} {name}")


if __name__ == "__main__":
    main()
