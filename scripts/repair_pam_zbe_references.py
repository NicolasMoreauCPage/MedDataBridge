#!/usr/bin/env python3
"""Ajoute les prérequis ZBE-1 aux scénarios PAM signalés par les ACK.

Par défaut, le script simule. ``--apply`` enregistre les nouvelles étapes. Les
scénarios restent inchangés lorsqu'un message INSERT portant déjà le même
ZBE-1 précède la correction ou l'annulation.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_reference_repair import (
    has_prior_original,
    reference_prerequisite_payloads,
    zbe1,
)


def _failed_reference_orders(report: dict) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for row in report.get("results", []):
        if row.get("qualification") != "corriger_pam":
            continue
        for step in row.get("steps", []):
            detail = step.get("source_ack_detail") or step.get("target_ack_detail") or ""
            if step.get("status") != "rejected":
                continue
            if "Original message with identifier" not in detail and "Mouvement original" not in detail:
                continue
            result.setdefault(row["key"], set()).add(int(step["order"]))
    return result


def main() -> None:
    args = sys.argv[1:]
    apply = "--apply" in args
    paths = [Path(arg).resolve() for arg in args if arg != "--apply"]
    if len(paths) != 1 or not paths[0].is_file():
        raise SystemExit("Usage: repair_pam_zbe_references.py RESULT.json [--apply]")
    references = _failed_reference_orders(json.loads(paths[0].read_text(encoding="utf-8")))
    repaired: list[tuple[str, int, int]] = []
    removed_prerequisites = 0
    with Session(engine) as session:
        for key, failed_orders in references.items():
            scenario = session.exec(select(InteropScenario).where(InteropScenario.key == key)).first()
            if not scenario:
                continue
            all_steps = session.exec(
                select(InteropScenarioStep)
                .where(InteropScenarioStep.scenario_id == scenario.id)
                .order_by(InteropScenarioStep.order_index, InteropScenarioStep.id)
            ).all()
            generated = [step for step in all_steps if (step.name or "").startswith("Prérequis ")]
            steps = [step for step in all_steps if step not in generated]
            # Les numéros d'étapes de l'ACK désignent l'ordre du catalogue
            # historique, avant injection des prérequis. Après avoir écarté
            # ces prérequis générés, l'index est donc à nouveau fiable, même
            # pour les imports dont les étapes ne s'appellent pas « Step N ».
            failed_steps = {
                steps[order - 1].id for order in failed_orders
                if 0 < order <= len(steps)
            }
            expanded: list[InteropScenarioStep] = []
            added = 0
            for index, step in enumerate(steps):
                if step.id in failed_steps and not has_prior_original(steps, index, zbe1(step.payload)):
                    for trigger, payload in reference_prerequisite_payloads(step):
                        added += 1
                        expanded.append(InteropScenarioStep(
                            scenario_id=scenario.id,
                            order_index=0,
                            name=f"Prérequis {trigger} — référence ZBE-1",
                            description=(
                                f"Mouvement original requis par l'étape {step.order_index}; "
                                f"ZBE-1={zbe1(step.payload)}."
                            ),
                            message_format="hl7",
                            message_type=f"ADT^{trigger}",
                            payload=payload,
                        ))
                expanded.append(step)
            if not added:
                continue
            repaired.append((scenario.key, len(failed_steps), added))
            if apply:
                for item in generated:
                    session.delete(item)
                    removed_prerequisites += 1
                for order, item in enumerate(expanded, 1):
                    item.order_index = order
                    session.add(item)
                scenario.updated_at = datetime.utcnow()
                scenario.version += 1
                session.add(scenario)
        if apply:
            session.commit()
    mode = "enregistré(s)" if apply else "détecté(s)"
    print(f"{len(repaired)} scénario(s) {mode}; {removed_prerequisites} prérequis généré(s) remplacé(s).")
    for key, references_count, prerequisites_count in repaired:
        print(f"- {key}: {references_count} référence(s), {prerequisites_count} prérequis")


if __name__ == "__main__":
    main()
