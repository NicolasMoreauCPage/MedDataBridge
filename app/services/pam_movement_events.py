"""Règles d'événements PAM dépendantes de l'historique de mouvements."""

from sqlmodel import Session, select

from app.models import Mouvement
from app.movement_type_mapping import to_standard_movement_code


def detect_nature_transition(session: Session, mouvement, operation: str) -> tuple[str | None, str | None]:
    """Détecte les conversions ambulatoire/hospitalisé A06 et A07."""
    if operation != "insert" or not getattr(mouvement, "venue_id", None):
        return None, None
    current_nature = getattr(mouvement, "nature", None)
    if current_nature not in {"H", "S"}:
        return None, None
    previous_movements = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == mouvement.venue_id)
        .where(Mouvement.when < mouvement.when)
        .order_by(Mouvement.when.desc())
    ).all()
    previous_nature = next(
        (getattr(previous, "nature", None) for previous in previous_movements if getattr(previous, "nature", None) in {"H", "S"}),
        None,
    )
    if previous_nature == "S" and current_nature == "H":
        return "A06", previous_nature
    if previous_nature == "H" and current_nature == "S":
        return "A07", previous_nature
    return None, previous_nature


def select_movement_event(session: Session, mouvement, operation: str) -> str:
    """Choisit le déclencheur ADT selon les priorités du profil PAM."""
    explicit_trigger = getattr(mouvement, "trigger_event", None)
    if explicit_trigger:
        return explicit_trigger

    transition_event, _ = detect_nature_transition(session, mouvement, operation)
    if transition_event:
        return transition_event

    mapped_event = to_standard_movement_code(getattr(mouvement, "movement_type", None), "hl7")
    if mapped_event:
        return mapped_event.split("^")[1] if "^" in mapped_event else "A99"

    if getattr(mouvement, "action", None) == "CANCEL":
        return {
            "A01": "A11", "A04": "A11", "A03": "A13", "A02": "A12",
            "A05": "A38", "A15": "A26", "A21": "A52", "A22": "A53",
            "A54": "A55", "A06": "A07", "A07": "A06",
        }.get(getattr(mouvement, "original_trigger", None), "A12")
    return "Z99" if operation == "update" else "A01"
