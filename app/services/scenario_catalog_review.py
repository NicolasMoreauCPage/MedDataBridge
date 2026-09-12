"""Analyse et application de la décision de conservation du catalogue."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep


DEFAULT_REPORT_PATH = Path(
    "artifacts/roundtrip-scenarios-two-ght-v12-final-corrections/result.json"
)

_REPORT_DECISIONS = {
    "conserver": ("approved", True, "Round-trip conforme : scénario conservé."),
    "corriger_sequence_pam": (
        "repairable",
        False,
        "Réparable mais désactivé : séquence PAM à réordonner ou à compléter avec ses prérequis.",
    ),
    "corriger_pam": (
        "repairable",
        False,
        "Réparable mais désactivé : écart PAM à diagnostiquer (séquence, prérequis ou contenu du message).",
    ),
    "corriger_hl7_siu": (
        "repairable",
        False,
        "Réparable mais désactivé : scénario HL7 v2 SIU de rendez-vous, hors périmètre IHE PAM.",
    ),
    "ajouter_prerequis_patient": (
        "repairable",
        False,
        "Réparable mais désactivé : ajouter le prérequis patient attendu avant l'étape concernée.",
    ),
    "corriger_moteur_hprim": (
        "repairable",
        False,
        "Réparable mais désactivé : écart du moteur HPRIM à traiter, scénario conservé pour preuve.",
    ),
    "retirer_du_roundtrip_positif": (
        "manual_review",
        False,
        "Test négatif conservé : rejet métier ou syntaxique attendu, hors parcours positif.",
    ),
    "a_qualifier": (
        "manual_review",
        False,
        "Désactivé en attente de qualification métier ou de correction manuelle du contenu.",
    ),
}


def _step_signature(steps: list[InteropScenarioStep]) -> str:
    """Signature stable du contenu fonctionnel, hors noms et identifiants SQL."""
    source = "\n---\n".join(
        ":".join(
            (
                (step.message_format or "").lower().strip(),
                (step.message_type or "").strip(),
                (step.payload or "").replace("\r\n", "\n").replace("\r", "\n").strip(),
            )
        )
        for step in sorted(steps, key=lambda item: (item.order_index, item.id or 0))
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def load_report_decisions(path: str | Path = DEFAULT_REPORT_PATH) -> dict[str, tuple[str, bool, str]]:
    """Lit les décisions du rapport de round-trip, indexées par clé stable."""
    report_path = Path(path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    decisions: dict[str, tuple[str, bool, str]] = {}
    for result in report.get("results", []):
        qualification = result.get("qualification")
        if qualification in _REPORT_DECISIONS and result.get("key"):
            decisions[result["key"]] = _REPORT_DECISIONS[qualification]
        # La clé technique peut évoluer lors d'un changement du normaliseur
        # d'import. Le checksum du contenu reste l'ancre stable du scénario.
        if qualification in _REPORT_DECISIONS and result.get("source_checksum"):
            decisions[f"checksum:{result['source_checksum']}"] = _REPORT_DECISIONS[qualification]
    return decisions


def _missing_key_name_decisions(
    path: str | Path,
    existing_keys: set[str],
) -> dict[str, tuple[str, bool, str]]:
    """Bridge only report keys absent from the current normalized catalogue.

    Names are not globally unique in the legacy HPRIM catalogue. They are used
    as a migration bridge solely for old report keys that are no longer present
    after a normalizer evolution; using them for every result would activate
    distinct scenarios sharing a historical filename.
    """
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    output: dict[str, tuple[str, bool, str]] = {}
    for result in report.get("results", []):
        qualification = result.get("qualification")
        if (
            result.get("key") not in existing_keys
            and result.get("name")
            and qualification in _REPORT_DECISIONS
        ):
            output.setdefault(result["name"], _REPORT_DECISIONS[qualification])
    return output


def _scenario_decision(
    scenario: InteropScenario,
    decisions: dict[str, tuple[str, bool, str]],
    missing_name_decisions: dict[str, tuple[str, bool, str]],
) -> tuple[str, bool, str] | None:
    if scenario.key in decisions:
        return decisions[scenario.key]
    if scenario.source_checksum and (decision := decisions.get(f"checksum:{scenario.source_checksum}")):
        return decision
    try:
        sources = json.loads(scenario.legacy_source_json or "[]")
    except json.JSONDecodeError:
        sources = []
    for source in sources if isinstance(sources, list) else []:
        if isinstance(source, dict) and source.get("name"):
            decision = missing_name_decisions.get(source["name"])
            if decision:
                return decision
    return None


def apply_catalog_review(
    session: Session,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> dict[str, int]:
    """Déduplique le catalogue et applique la politique active/inactive.

    Un seul scénario est conservé par contenu identique. Les décisions du
    rapport priment sur les imports non qualifiés : seul ``approved`` reste
    actif. Les scénarios réparables, non évalués ou en doublon restent
    éditables, mais sont désactivés pour les campagnes et les émissions de
    masse jusqu'à leur qualification explicite.
    """
    decisions = load_report_decisions(report_path)
    scenarios = session.exec(select(InteropScenario).order_by(InteropScenario.id)).all()
    missing_name_decisions = _missing_key_name_decisions(
        report_path, {item.key for item in scenarios}
    )
    steps_by_scenario: dict[int, list[InteropScenarioStep]] = defaultdict(list)
    for step in session.exec(select(InteropScenarioStep)).all():
        steps_by_scenario[step.scenario_id].append(step)

    grouped: dict[str, list[InteropScenario]] = defaultdict(list)
    for scenario in scenarios:
        grouped[_step_signature(steps_by_scenario[scenario.id])].append(scenario)

    review_by_scenario = {
        item.scenario_id: item for item in session.exec(select(ScenarioCatalogReview)).all()
    }
    now = datetime.utcnow()
    counters: dict[str, int] = defaultdict(int)

    for candidates in grouped.values():
        # A decision backed by the catalogue report is preferred over an older
        # direct import. Then prefer active data, legacy key and lowest id.
        def priority(item: InteropScenario) -> tuple[int, int, int, int]:
            status = (
                _scenario_decision(item, decisions, missing_name_decisions)
                or ("unassessed", False, "")
            )[0]
            return (
                2 if status == "approved" else 1 if status == "repairable" else 0,
                int(bool(item.is_active)),
                int((item.key or "").startswith("legacy.")),
                -(item.id or 0),
            )

        canonical = max(candidates, key=priority)
        for scenario in candidates:
            if scenario.id != canonical.id:
                status, should_be_active, note = (
                    "duplicate",
                    False,
                    f"Doublon strict du scénario #{canonical.id} « {canonical.name} ».",
                )
            elif decision := _scenario_decision(scenario, decisions, missing_name_decisions):
                status, should_be_active, note = decision
            else:
                status, should_be_active, note = (
                    "unassessed",
                    False,
                    "Hors de la campagne de round-trip de référence : à examiner manuellement.",
                )

            scenario.is_active = should_be_active
            scenario.updated_at = now
            session.add(scenario)

            review = review_by_scenario.get(scenario.id)
            if not review:
                review = ScenarioCatalogReview(scenario_id=scenario.id)
            review.status, review.note = status, note
            review.source_report, review.reviewed_at = str(report_path), now
            session.add(review)
            counters[status] += 1

    session.commit()
    counters["active"] = sum(1 for item in scenarios if item.is_active)
    counters["inactive"] = len(scenarios) - counters["active"]
    return dict(counters)
