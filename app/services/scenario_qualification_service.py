"""Services métier du catalogue et de la qualification par logiciel cible."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models_qualification import ScenarioTargetState, ScenarioTheme, ScenarioThemeAssignment
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlay, ScenarioPlayTarget
from app.models_scenarios import InteropScenario


LEGACY_VARIABLES = re.compile(r"\$[A-Za-z][A-Za-z0-9_]*\$")


def _json_value(raw: Optional[str], expected_type: type) -> object | None:
    try:
        value = json.loads(raw or "null")
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, expected_type) else None


def publication_issues(scenario: InteropScenario) -> list[str]:
    """Retourne les métadonnées manquantes pour une publication qualifiable."""
    issues: list[str] = []
    if not (scenario.functional_comment or "").strip():
        issues.append("Ajoutez l'intention métier dans le commentaire fonctionnel.")

    preconditions = _json_value(scenario.preconditions_json, list)
    if not preconditions:
        issues.append("Définissez au moins une précondition exécutable.")

    scenario_assertions = _json_value(scenario.assertions_json, list) or []
    step_assertions = [
        assertion
        for step in scenario.steps or []
        for assertion in (_json_value(step.assertions_json, list) or [])
    ]
    if not scenario_assertions and not step_assertions:
        issues.append("Définissez au moins une assertion exécutable.")

    expected_outcome = _json_value(scenario.expected_outcome_json, dict)
    if not expected_outcome:
        issues.append("Décrivez explicitement le résultat métier attendu.")
    return issues


def target_key(value: Optional[str]) -> str:
    """Normalise la clé fonctionnelle d'un logiciel sans modifier son libellé."""
    return (value or "cible-non-definie").strip() or "cible-non-definie"


def get_target_state(session: Session, scenario_id: int, system_key: str, *, create: bool = True) -> Optional[ScenarioTargetState]:
    system_key = target_key(system_key)
    state = session.exec(
        select(ScenarioTargetState)
        .where(ScenarioTargetState.scenario_id == scenario_id)
        .where(ScenarioTargetState.target_system_key == system_key)
    ).first()
    if not state and create:
        state = ScenarioTargetState(scenario_id=scenario_id, target_system_key=system_key)
        session.add(state)
        session.flush()
    return state


def _target_delivery_statuses(session: Session, play: ScenarioPlay, system_key: str) -> list[str]:
    targets = session.exec(
        select(ScenarioPlayTarget)
        .where(ScenarioPlayTarget.play_id == play.id)
        .where(ScenarioPlayTarget.target_system_key == system_key)
    ).all()
    endpoint_ids = [target.endpoint_id for target in targets]
    if not endpoint_ids:
        return []
    deliveries = session.exec(
        select(ScenarioDelivery)
        .where(ScenarioDelivery.play_id == play.id)
        .where(ScenarioDelivery.endpoint_id.in_(endpoint_ids))
    ).all()
    return [delivery.status for delivery in deliveries if delivery.status != "skipped"]


def refresh_target_state(session: Session, scenario_id: int, system_key: str) -> ScenarioTargetState:
    """Recalcule un état à partir des jeux réels, sans écraser l'historique."""
    system_key = target_key(system_key)
    state = get_target_state(session, scenario_id, system_key, create=True)
    assert state is not None
    plays = session.exec(
        select(ScenarioPlay)
        .where(ScenarioPlay.scenario_id == scenario_id)
        .where(ScenarioPlay.dry_run == False)  # noqa: E712
        .where(ScenarioPlay.finished_at.is_not(None))
        .order_by(ScenarioPlay.finished_at.desc(), ScenarioPlay.id.desc())
    ).all()
    relevant: list[tuple[ScenarioPlay, list[str]]] = []
    for play in plays:
        statuses = _target_delivery_statuses(session, play, system_key)
        if statuses:
            relevant.append((play, statuses))
    previous = state.status
    if not relevant:
        state.status, state.last_run_at, state.last_play_id = "never_run", None, None
        state.consecutive_failures = 0
    else:
        play, statuses = relevant[0]
        if all(status == "sent" for status in statuses):
            outcome = "success"
        elif any(status == "sent" for status in statuses):
            outcome = "partial"
        else:
            outcome = "error"
        state.status, state.last_run_at, state.last_play_id = outcome, play.finished_at, play.id
        if outcome == "success":
            state.last_success_at, state.consecutive_failures = play.finished_at, 0
        else:
            state.last_failure_at = play.finished_at
            state.consecutive_failures = sum(
                1
                for _, run_statuses in relevant
                if not all(status == "sent" for status in run_statuses)
            )
    if state.status != previous:
        state.status_since = datetime.utcnow()
    state.updated_at = datetime.utcnow()
    session.add(state)
    session.flush()
    return state


def refresh_play_target_states(session: Session, play_id: int) -> None:
    """Synchronise les statuts des cibles d'un jeu, puis leur état courant."""
    play = session.get(ScenarioPlay, play_id)
    if not play:
        return
    targets = session.exec(select(ScenarioPlayTarget).where(ScenarioPlayTarget.play_id == play_id)).all()
    for current in targets:
        statuses = _target_delivery_statuses(session, play, target_key(current.target_system_key))
        if not statuses:
            current.status = "skipped"
        elif all(status in {"sent", "dry_run"} for status in statuses):
            current.status = "success" if not play.dry_run else "dry_run"
        elif any(status in {"queued", "pending", "retry"} for status in statuses):
            current.status = "scheduled"
        elif any(status in {"sent", "dry_run"} for status in statuses):
            current.status = "partial"
        else:
            current.status = "error"
        current.updated_at = datetime.utcnow()
        session.add(current)
        if not play.dry_run:
            refresh_target_state(session, play.scenario_id, target_key(current.target_system_key))
    session.flush()


def set_target_active(session: Session, scenario_id: int, system_key: str, active: bool) -> ScenarioTargetState:
    state = get_target_state(session, scenario_id, system_key, create=True)
    assert state is not None
    state.is_active, state.updated_at = active, datetime.utcnow()
    session.add(state)
    session.commit()
    return state


def record_target_outcome(
    session: Session, scenario_id: int, system_key: str, status: str, *, run_at: Optional[datetime] = None
) -> ScenarioTargetState:
    """Enregistre aussi les campagnes historiques, qui ont leur propre runner."""
    state = get_target_state(session, scenario_id, system_key, create=True)
    assert state is not None
    normalized = "success" if status in {"success", "passed"} else "partial" if status == "partial" else "error"
    at = run_at or datetime.utcnow()
    if state.status != normalized:
        state.status_since = at
    state.status, state.last_run_at, state.updated_at = normalized, at, at
    if normalized == "success":
        state.last_success_at, state.consecutive_failures = at, 0
    else:
        state.last_failure_at = at
        state.consecutive_failures += 1
    session.add(state)
    session.flush()
    return state


def list_target_states(session: Session, system_key: Optional[str] = None) -> list[ScenarioTargetState]:
    query = select(ScenarioTargetState).order_by(ScenarioTargetState.target_system_key, ScenarioTargetState.status, ScenarioTargetState.scenario_id)
    if system_key:
        query = query.where(ScenarioTargetState.target_system_key == target_key(system_key))
    return session.exec(query).all()


def ensure_theme(session: Session, key: str, name: str, *, parent_key: Optional[str] = None, description: Optional[str] = None) -> ScenarioTheme:
    theme = session.exec(select(ScenarioTheme).where(ScenarioTheme.key == key)).first()
    parent_id = None
    if parent_key:
        parent = session.exec(select(ScenarioTheme).where(ScenarioTheme.key == parent_key)).first()
        parent_id = parent.id if parent else None
    if not theme:
        theme = ScenarioTheme(key=key, name=name, parent_id=parent_id, description=description)
    else:
        theme.name, theme.parent_id, theme.description = name, parent_id, description or theme.description
        theme.updated_at = datetime.utcnow()
    session.add(theme)
    session.flush()
    return theme


def assign_theme(session: Session, scenario_id: int, theme_id: int, *, primary: bool = True) -> ScenarioThemeAssignment:
    if primary:
        for previous in session.exec(select(ScenarioThemeAssignment).where(ScenarioThemeAssignment.scenario_id == scenario_id)).all():
            previous.is_primary = False
            session.add(previous)
    assignment = session.exec(
        select(ScenarioThemeAssignment)
        .where(ScenarioThemeAssignment.scenario_id == scenario_id)
        .where(ScenarioThemeAssignment.theme_id == theme_id)
    ).first()
    if not assignment:
        assignment = ScenarioThemeAssignment(scenario_id=scenario_id, theme_id=theme_id, is_primary=primary)
    else:
        assignment.is_primary = primary
    session.add(assignment)
    session.flush()
    return assignment


def theme_tree(session: Session) -> list[dict]:
    themes = session.exec(select(ScenarioTheme).where(ScenarioTheme.is_active == True).order_by(ScenarioTheme.order_index, ScenarioTheme.name)).all()  # noqa: E712
    children: dict[Optional[int], list[ScenarioTheme]] = defaultdict(list)
    for theme in themes:
        children[theme.parent_id].append(theme)

    def node(theme: ScenarioTheme) -> dict:
        return {"theme": theme, "children": [node(child) for child in children[theme.id]]}
    return [node(theme) for theme in children[None]]


def preflight_issues(scenario: InteropScenario) -> list[dict[str, str]]:
    """Contrôles non bloquants du catalogue, visibles avant un envoi réel."""
    issues: list[dict[str, str]] = []
    if not scenario.is_active:
        issues.append({"level": "error", "message": "Scénario désactivé."})
    if not scenario.functional_comment:
        issues.append({"level": "warning", "message": "Commentaire fonctionnel manquant."})
    existing_messages = {issue["message"] for issue in issues}
    for message in publication_issues(scenario):
        if message not in existing_messages:
            issues.append({"level": "warning", "message": message})
    for step in scenario.steps or []:
        fmt = (step.message_format or "hl7").lower()
        if fmt in {"hprim", "hprimxml"}:
            issues.append({"level": "warning", "message": f"Étape #{step.order_index}: format historique {fmt}, normalisé à XML lors de l'envoi."})
        if fmt in {"xml", "hprim", "hprimxml"}:
            xml_payload = re.sub(r"^\s*MSH\|(?=<)", "", step.payload or "")
            try:
                ET.fromstring(xml_payload)
            except ET.ParseError as exc:
                issues.append({"level": "error", "message": f"Étape #{step.order_index}: XML HPRIM invalide ({exc})."})
        variables = sorted(set(LEGACY_VARIABLES.findall(step.payload or "")))
        supported = {"$IPP$", "$NIP$", "$NDA$", "$VENUE$", "$UF$", "$DATE$", "$HEURE$", "$RPPS$", "$ADELI$", "$NOM$", "$PRENOM$", "$DOSSIER$", "$EMETTEUR$", "$INTERVENTION$", "$IDACTE$", "$ACTE$", "$PSC$", "$ADELI2$", "$ADELI_EXT$", "$CODE_SIH$", "$ESPACE_DE_NOM_MEDECIN_SIH$", "$GR$", "$UF_EXT$", "$CAISSE$", "$CENTRE$", "$EXERCICE$", "$FINESS$", "$MONTANTLOT11$", "$NUMLOT$", "$NUMSECU$", "$NUMTITRE$", "$NOMBENEFICIAIRE$", "$PRENOMBENEFICIAIRE$", "$DATENAISSANCE$", "$DATETRAITEMENT$"}
        unsupported = [item for item in variables if item.upper() not in supported]
        if unsupported:
            issues.append({"level": "warning", "message": f"Étape #{step.order_index}: variables historiques à renseigner: {', '.join(unsupported)}."})
    return issues
