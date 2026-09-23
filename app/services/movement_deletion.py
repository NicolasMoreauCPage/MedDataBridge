"""Suppression d'un mouvement avec notification injectée."""

from collections.abc import Callable

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models import Dossier, Mouvement, Venue


class MovementDeletionError(LookupError):
    """Le mouvement à supprimer n'existe pas."""


def delete_patient_movement(
    session: Session,
    *,
    movement_id: int,
    before_delete: Callable[[Mouvement], None],
) -> int:
    """Charge le contexte, notifie puis supprime le mouvement."""

    movement = session.exec(
        select(Mouvement)
        .options(
            selectinload(Mouvement.venue)
            .selectinload(Venue.dossier)
            .selectinload(Dossier.patient)
        )
        .where(Mouvement.id == movement_id)
    ).one_or_none()
    if movement is None:
        raise MovementDeletionError("Mouvement introuvable")

    venue_id = movement.venue_id
    before_delete(movement)
    session.delete(movement)
    session.commit()
    return venue_id


__all__ = ["MovementDeletionError", "delete_patient_movement"]
