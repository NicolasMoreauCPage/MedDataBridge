"""Règles d'événements PAM dépendantes de l'historique de mouvements."""

from sqlmodel import Session, select

from app.models import Mouvement


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
