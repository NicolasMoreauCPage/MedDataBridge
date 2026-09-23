"""Projection de la fiche détaillée d'un mouvement."""

from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models import Dossier, Mouvement, Venue
from app.models_structure import Chambre, Lit, UniteFonctionnelle, UniteHebergement
from app.services.vocabulary_lookup import get_vocabulary_options


class MovementDetailsError(LookupError):
    """Le mouvement demandé n'existe pas."""


@dataclass(frozen=True)
class MovementDetails:
    movement: Mouvement
    type_label: str
    uf_responsable_label: str | None
    uf_soins_label: str | None
    uf_hebergement_label: str | None
    chambre_info: str | None
    lit_info: str | None
    movement_type_options: list[dict[str, str]]


def _label(entity: object | None) -> str | None:
    if entity is None:
        return None
    short_name = getattr(entity, "short_name", None)
    return short_name.strip() if short_name and short_name.strip() else (
        getattr(entity, "name", None) or getattr(entity, "identifier", None)
    )


def _load_location(
    session: Session,
    location: str | None,
) -> tuple[UniteHebergement | None, Chambre | None, Lit | None]:
    if not location:
        return None, None, None
    parts = [part.strip() for part in location.split("^")]
    if len(parts) >= 2:
        uh_identifier = parts[0]
        uh = session.exec(
            select(UniteHebergement).where(
                or_(
                    UniteHebergement.identifier == uh_identifier,
                    UniteHebergement.identifier == f"UH-{uh_identifier}",
                )
            )
        ).first()
        chambre = (
            session.exec(
                select(Chambre).where(Chambre.identifier == parts[1])
            ).first()
            if parts[1]
            else None
        )
        lit = (
            session.exec(select(Lit).where(Lit.identifier == parts[2])).first()
            if len(parts) >= 3 and parts[2]
            else None
        )
        return uh, chambre, lit

    chambre = session.exec(
        select(Chambre).where(Chambre.identifier == location.strip())
    ).first()
    if chambre is None:
        return None, None, None
    uh = (
        session.get(UniteHebergement, chambre.unite_hebergement_id)
        if chambre.unite_hebergement_id
        else None
    )
    return uh, chambre, None


def load_movement_details(session: Session, movement_id: int) -> MovementDetails:
    """Charge le mouvement et calcule les libellés nécessaires à sa fiche."""

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
        raise MovementDetailsError("Mouvement introuvable")

    uf_identifiers = {
        identifier
        for identifier in (movement.uf_responsabilite, movement.uf_soins_code)
        if identifier
    }
    ufs = (
        session.exec(
            select(UniteFonctionnelle).where(
                UniteFonctionnelle.identifier.in_(uf_identifiers)
            )
        ).all()
        if uf_identifiers
        else []
    )
    uf_by_identifier = {uf.identifier: uf for uf in ufs}
    uf_responsable_label = _label(
        uf_by_identifier.get(movement.uf_responsabilite)
    )
    uf_soins_label = movement.uf_soins_label or _label(
        uf_by_identifier.get(movement.uf_soins_code)
    )

    uh, chambre, lit = _load_location(session, movement.location)
    uf_hebergement = None
    if uh is not None and uh.unite_fonctionnelle_id:
        uf_hebergement = session.get(
            UniteFonctionnelle, uh.unite_fonctionnelle_id
        )

    type_options = get_vocabulary_options("movement-nature") or []
    type_label = next(
        (
            option.get("label")
            for option in type_options
            if option.get("value") == movement.movement_type
        ),
        None,
    )
    return MovementDetails(
        movement=movement,
        type_label=type_label or movement.movement_type or "Non spécifié",
        uf_responsable_label=uf_responsable_label,
        uf_soins_label=uf_soins_label,
        uf_hebergement_label=_label(uf_hebergement),
        chambre_info=_label(chambre),
        lit_info=_label(lit),
        movement_type_options=type_options,
    )


__all__ = ["MovementDetails", "MovementDetailsError", "load_movement_details"]
