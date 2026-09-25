"""Réparation explicite des références ZBE-1 des scénarios PAM.

Un Z99 ou un message d'annulation désigne toujours le mouvement d'origine par
son ZBE-1.  Cette règle ne doit jamais être remplacée par un rapprochement
heuristique sur le dernier mouvement reçu.  Pour rendre un extrait historique
rejouable seul, ce module construit les prérequis PAM minimaux qui créent ce
mouvement avec le même ZBE-1.
"""

from __future__ import annotations

from collections import deque

from app.models.scenarios import InteropScenarioStep
from app.state_transitions import ALLOWED_TRANSITIONS, IDENTITY_ONLY_TRIGGERS, INITIAL_EVENTS


def _normalize(payload: str) -> list[str]:
    return [line for line in payload.replace("\\r", "\r").replace("\n", "\r").replace("\r\n", "\r").split("\r") if line]


def _field(payload: str, segment: str, field: int) -> str:
    for line in _normalize(payload):
        if line.startswith(f"{segment}|"):
            values = line.split("|")
            return values[field] if len(values) > field else ""
    return ""


def _set_field(payload: str, segment: str, field: int, value: str) -> str:
    lines = _normalize(payload)
    for index, line in enumerate(lines):
        if not line.startswith(f"{segment}|"):
            continue
        values = line.split("|")
        while len(values) <= field:
            values.append("")
        values[field] = value
        lines[index] = "|".join(values)
        break
    return "\r".join(lines)


def set_message_trigger(payload: str, trigger: str) -> str:
    """Remplace MSH-9 (index 8 après le découpage de la ligne MSH)."""
    lines = _normalize(payload)
    for index, line in enumerate(lines):
        if not line.startswith("MSH|"):
            continue
        values = line.split("|")
        while len(values) <= 8:
            values.append("")
        values[8] = f"ADT^{trigger}"
        lines[index] = "|".join(values)
        break
    return "\r".join(lines)


def zbe1(payload: str) -> str:
    return _field(payload, "ZBE", 1).split("^", 1)[0].strip()


def zbe_action(payload: str) -> str:
    return _field(payload, "ZBE", 4).strip().upper()


def _trigger(payload: str) -> str:
    # Dans une ligne MSH découpée par ``|``, MSH-9 est à l'index 8 :
    # MSH-1 est déjà le séparateur immédiatement après le nom du segment.
    message_type = _field(payload, "MSH", 8)
    return message_type.split("^", 2)[1].strip().upper() if "^" in message_type else ""


def _original_trigger(step: InteropScenarioStep) -> str:
    original = _field(step.payload, "ZBE", 6).split("^", 1)[0].strip().upper()
    if original in ALLOWED_TRANSITIONS or original in INITIAL_EVENTS:
        return original
    return {
        "A11": "A01", "A12": "A02", "A13": "A03", "A23": "A06", "A38": "A05",
    }.get(_trigger(step.payload), "A01")


def pam_path_to(trigger: str) -> list[str] | None:
    """Chemin PAM minimal depuis le début du parcours vers ``trigger``."""
    if trigger in IDENTITY_ONLY_TRIGGERS or not trigger:
        return None
    queue: deque[list[str]] = deque([[event] for event in sorted(INITIAL_EVENTS)])
    visited = set(INITIAL_EVENTS)
    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == trigger:
            return path
        if len(path) >= 6:
            continue
        for following in sorted(ALLOWED_TRANSITIONS.get(current, set())):
            if following in visited or following in IDENTITY_ONLY_TRIGGERS:
                continue
            visited.add(following)
            queue.append([*path, following])
    return None


def reference_prerequisite_payloads(step: InteropScenarioStep) -> list[tuple[str, str]]:
    """Retourne les messages INSERT à insérer avant une correction/annulation.

    Le dernier prérequis porte exactement le ZBE-1 référencé par le message
    source. Les prérequis de transition éventuels reçoivent un identifiant
    technique distinct afin qu'ils ne brouillent pas cette corrélation.
    """
    movement_id = zbe1(step.payload)
    if not movement_id or not any(line.startswith("ZBE|") for line in _normalize(step.payload)):
        return []
    target_trigger = _original_trigger(step)
    path = pam_path_to(target_trigger)
    if not path:
        return []
    result: list[tuple[str, str]] = []
    for index, trigger in enumerate(path, 1):
        payload = set_message_trigger(step.payload, trigger)
        source_id = movement_id if index == len(path) else f"PREREQ-{step.id or step.order_index}-{index}"
        payload = _set_field(payload, "ZBE", 1, source_id)
        payload = _set_field(payload, "ZBE", 4, "INSERT")
        payload = _set_field(payload, "ZBE", 6, "")
        result.append((trigger, payload))
    return result


def has_prior_original(steps: list[InteropScenarioStep], position: int, movement_id: str) -> bool:
    """Indique si un INSERT antérieur crée déjà ce ZBE-1 dans le scénario."""
    for step in steps[:position]:
        if zbe1(step.payload) == movement_id and zbe_action(step.payload) == "INSERT":
            return True
    return False
