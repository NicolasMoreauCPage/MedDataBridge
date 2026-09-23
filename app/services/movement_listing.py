"""Chargement filtré des mouvements et de leur contexte de navigation."""

from dataclasses import dataclass

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models import Dossier, Mouvement, Venue


class MovementListContextError(LookupError):
    def __init__(self, status_code: int, title: str, message: str, back_url: str):
        super().__init__(message)
        self.status_code = status_code
        self.title = title
        self.message = message
        self.back_url = back_url


@dataclass(frozen=True)
class MovementListResult:
    movements: list[Mouvement]
    venue: Venue | None
    dossier: Dossier | None


def load_movement_list(
    session: Session,
    *,
    venue_id: int | None,
    dossier_id: int | None,
    ej_id: int | None,
    include_cancelled: bool,
    order: str,
    movement_type: str | None,
    status: str | None,
    location_filter: str | None,
) -> MovementListResult:
    """Construit une requête unique pour le périmètre et les filtres demandés."""

    venue = None
    dossier = None
    if venue_id is not None:
        venue = session.exec(
            select(Venue)
            .options(selectinload(Venue.dossier).selectinload(Dossier.patient))
            .where(Venue.id == venue_id)
        ).one_or_none()
        if venue is None:
            raise MovementListContextError(
                404,
                "Venue introuvable",
                "La venue spécifiée n'existe pas. Veuillez sélectionner une venue valide.",
                "/dossiers",
            )
        dossier = venue.dossier
        statement = select(Mouvement).where(Mouvement.venue_id == venue_id)
    elif dossier_id is not None:
        dossier = session.exec(
            select(Dossier)
            .options(selectinload(Dossier.patient))
            .where(Dossier.id == dossier_id)
        ).one_or_none()
        if dossier is None:
            raise MovementListContextError(
                404,
                "Dossier introuvable",
                "Le dossier spécifié n'existe pas. Veuillez sélectionner un dossier valide.",
                "/dossiers",
            )
        statement = select(Mouvement).join(Venue).where(Venue.dossier_id == dossier_id)
    elif ej_id is not None:
        statement = (
            select(Mouvement)
            .join(Venue, Venue.id == Mouvement.venue_id)
            .join(Dossier, Dossier.id == Venue.dossier_id)
            .where(Dossier.entite_juridique_id == ej_id)
        )
    else:
        raise MovementListContextError(
            400,
            "Paramètre manquant",
            "Vous devez spécifier soit un dossier_id soit un venue_id pour voir les mouvements.",
            "/dossiers",
        )

    if not include_cancelled:
        statement = statement.where(
            Mouvement.status.is_(None) | (Mouvement.status != "cancelled")
        )
    if movement_type:
        statement = statement.where(Mouvement.type == movement_type)
    if status:
        statement = statement.where(Mouvement.status == status)
    if location_filter:
        statement = statement.where(Mouvement.location.ilike(f"%{location_filter}%"))
    if order == "desc":
        statement = statement.order_by(Mouvement.when.desc(), Mouvement.id.desc())
    else:
        statement = statement.order_by(Mouvement.when.asc(), Mouvement.id.asc())

    return MovementListResult(
        movements=list(session.exec(statement).all()),
        venue=venue,
        dossier=dossier,
    )


__all__ = ["MovementListContextError", "MovementListResult", "load_movement_list"]
