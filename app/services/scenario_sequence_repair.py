"""Réparation prudente par réordonnancement des séquences IHE PAM.

Le service ne modifie jamais le contenu d'un message. Il propose uniquement
une permutation des étapes ADT d'un scénario mono-patient lorsque cette
permutation satisfait exactement l'automate PAM.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Sequence

from app.models.scenarios import InteropScenarioStep
from app.services.mllp import parse_msh_fields
from app.state_transitions import IDENTITY_ONLY_TRIGGERS, is_valid_transition


def _patient_identifier(payload: str) -> Optional[str]:
    for segment in payload.replace("\\r", "\r").replace("\n", "\r").replace("\r\n", "\r").split("\r"):
        if segment.startswith("PID|"):
            fields = segment.split("|")
            return fields[3].split("^")[0].strip() if len(fields) > 3 and fields[3] else None
    return None


def _trigger(step: InteropScenarioStep) -> Optional[str]:
    msh = parse_msh_fields(step.payload or "")
    return msh.get("trigger") if msh.get("type") == "ADT" else None


def repaired_step_order(steps: Sequence[InteropScenarioStep]) -> list[InteropScenarioStep] | None:
    """Retourne un ordre PAM valide ou ``None`` si une réparation sûre est impossible.

    Les scénarios mixtes, multi-patients ou longs sont laissés au travail
    manuel : réordonner automatiquement leurs messages pourrait modifier leur
    sens fonctionnel même si l'automate PAM les accepte.
    """
    ordered = sorted(steps, key=lambda item: (item.order_index, item.id or 0))
    if not ordered or any((item.message_format or "hl7").lower() != "hl7" for item in ordered):
        return None
    movement_positions: list[int] = []
    events: list[str] = []
    patient_ids: set[str] = set()
    for position, step in enumerate(ordered):
        trigger = _trigger(step)
        if not trigger or trigger in IDENTITY_ONLY_TRIGGERS:
            continue
        movement_positions.append(position)
        events.append(trigger)
        if patient_id := _patient_identifier(step.payload or ""):
            patient_ids.add(patient_id)
    if not events or len(events) > 12 or len(patient_ids) > 1:
        return None

    @lru_cache(maxsize=None)
    def search(previous: Optional[str], remaining: tuple[int, ...]) -> tuple[int, ...] | None:
        if not remaining:
            return ()
        # Préférer les éléments les plus proches de leur position originelle,
        # pour obtenir la correction minimale lorsqu'il existe plusieurs ordres.
        for index in remaining:
            event = events[index]
            if not is_valid_transition(previous, event):
                continue
            tail = search(event, tuple(item for item in remaining if item != index))
            if tail is not None:
                return (index, *tail)
        return None

    permutation = search(None, tuple(range(len(events))))
    if permutation is None or list(permutation) == list(range(len(events))):
        return None
    repaired = list(ordered)
    source_steps = [ordered[position] for position in movement_positions]
    for position, event_index in zip(movement_positions, permutation):
        repaired[position] = source_steps[event_index]
    return repaired


def apply_repaired_step_order(steps: Sequence[InteropScenarioStep]) -> bool:
    """Réécrit des indices denses lorsque ``repaired_step_order`` est possible."""
    repaired = repaired_step_order(steps)
    if not repaired:
        return False
    for index, step in enumerate(repaired, 1):
        step.order_index = index
    return True
