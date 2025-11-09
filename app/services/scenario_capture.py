"""Service de capture d'un dossier en scénario HL7.

Approche initiale (MVP):
 - Récupère le dossier + mouvements triés chronologiquement.
 - Pour chaque mouvement, tente de retrouver un MessageLog correspondant (type ADT^X) dans une fenêtre ±5 min.
 - Si trouvé, réutilise le payload original comme step.
 - Sinon génère un message HL7 minimal avec placeholders (IPP/NDA à remplacer lors du replay).
 - Calcule delay_seconds à partir de l'intervalle avec le mouvement précédent.

Évolutions futures:
 - Corrélation plus fine (matching PV1/ZBE).
 - Capture FHIR si présent.
 - Inclusion des modifications identité (A08) et annulations.
 - Options pour exclure certains événements ou compresser les délais longs.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List

from sqlmodel import Session, select

from app.models import Dossier, Mouvement
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_shared import MessageLog


def _find_matching_message(session: Session, trigger: str, when: datetime) -> Optional[MessageLog]:
    """Recherche best-effort d'un MessageLog ADT^trigger proche du timestamp 'when'."""
    window_start = when - timedelta(minutes=5)
    window_end = when + timedelta(minutes=5)
    stmt = (
        select(MessageLog)
        .where(MessageLog.kind == "MLLP")
        .where(MessageLog.message_type.like(f"ADT%{trigger}"))
        .where(MessageLog.created_at >= window_start)
        .where(MessageLog.created_at <= window_end)
        .order_by(MessageLog.created_at.asc())
    )
    return session.exec(stmt).first()


def _generate_minimal_hl7(now: datetime, trigger: str, control_id: str) -> str:
    ts = now.strftime("%Y%m%d%H%M%S")
    # Minimal MSH + EVN + PID + PV1 skeleton; placeholders for identifiers.
    return (
        f"MSH|^~\\&|CAP|LOCAL|REC|LOCAL|{ts}||ADT^{trigger}|{control_id}|P|2.5\r"
        f"EVN|{trigger}|{ts}\r"
        "PID|1||PLACEHOLDER-IPP^^^CAPTURE&1.2.3&ISO^PI||Doe^John\r"
        "PV1|1|I|||||||||||||||||PLACEHOLDER-NDA^^^CAPTURE&1.2.3&ISO^VN\r"
    )


def capture_dossier_as_scenario(
    session: Session,
    dossier: Dossier,
    *,
    key: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    include_discharge: bool = True,
) -> InteropScenario:
    """Construit et persiste un scénario à partir des mouvements d'un dossier."""
    # Préparer métadonnées scénario
    key = key or f"capture/dossier/{dossier.id}/{datetime.utcnow().isoformat()}"
    name = name or f"Capture Dossier {dossier.dossier_seq}"
    description = description or "Scénario reconstruit à partir des mouvements du dossier (MVP)."

    scenario = InteropScenario(
        key=key,
        name=name,
        description=description,
        protocol="HL7",
        category="capture",
        tags="capture,auto",
    )
    session.add(scenario)
    session.commit(); session.refresh(scenario)

    # Récupérer mouvements triés
    mouvements: List[Mouvement] = (
        session.exec(
            select(Mouvement).where(Mouvement.venue_id.in_([v.id for v in dossier.venues])).order_by(Mouvement.when.asc())
        ).all()
        if dossier.venues else []
    )
    if not mouvements:
        # Fallback: aucun mouvement -> créer step unique admission synthétique
        payload = _generate_minimal_hl7(dossier.admit_time, "A01", f"CAP{dossier.id}A01")
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=1,
            message_format="hl7",
            message_type="ADT^A01",
            payload=payload,
            delay_seconds=None,
            name="Admission (synthetic)",
        )
        session.add(step); session.commit()
        return scenario

    prev_when: Optional[datetime] = None
    order_index = 1
    for mouv in mouvements:
        trigger = mouv.trigger_event or (mouv.type.split("^")[1] if mouv.type and "^" in mouv.type else "A01")
        matching = _find_matching_message(session, trigger, mouv.when)
        control_id = f"CAP{mouv.id}{trigger}"
        payload = matching.payload if matching else _generate_minimal_hl7(mouv.when, trigger, control_id)
        delay_seconds = None
        if prev_when:
            diff = (mouv.when - prev_when).total_seconds()
            delay_seconds = int(diff) if diff > 0 else 0
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=order_index,
            message_format="hl7",
            message_type=f"ADT^{trigger}",
            payload=payload,
            delay_seconds=delay_seconds,
            name=f"{trigger} mouvement #{mouv.id}",
        )
        session.add(step)
        order_index += 1
        prev_when = mouv.when
    session.commit()
    return scenario
