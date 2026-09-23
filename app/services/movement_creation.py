"""Cas d'usage transactionnel de création d'un mouvement patient."""

from datetime import datetime

from sqlmodel import Session, select

from app.db import get_next_sequence
from app.models import Mouvement, Venue
from app.models_structure import Chambre, Lit, UniteFonctionnelle, UniteHebergement
from app.services.movement_form_context import EVENT_METADATA
from app.state_transitions import ALLOWED_TRANSITIONS, INITIAL_EVENTS


class MovementCreationError(ValueError):
    """Erreur métier pouvant être convertie en réponse HTTP 400 ou 404."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def parse_movement_event(type_code: str) -> str:
    parts = type_code.split("^", 1)
    if len(parts) != 2 or parts[0] != "ADT" or not parts[1]:
        raise MovementCreationError(
            "Le type de mouvement doit être un événement ADT valide (ADT^Axx)."
        )
    return parts[1]


def load_movement_location(
    session: Session,
    *,
    uh_id: int | None,
    chambre_id: int | None,
    lit_id: int | None,
) -> tuple[UniteHebergement | None, Chambre | None, Lit | None]:
    lit = session.get(Lit, lit_id) if lit_id is not None else None
    if lit_id is not None and lit is None:
        raise MovementCreationError("Le lit sélectionné n'existe pas.")

    effective_chambre_id = chambre_id or (lit.chambre_id if lit else None)
    chambre = (
        session.get(Chambre, effective_chambre_id)
        if effective_chambre_id is not None
        else None
    )
    if chambre_id is not None and chambre is None:
        raise MovementCreationError("La chambre sélectionnée n'existe pas.")
    if lit is not None and chambre is not None and lit.chambre_id != chambre.id:
        raise MovementCreationError("Le lit sélectionné n'appartient pas à la chambre.")

    effective_uh_id = uh_id or (
        chambre.unite_hebergement_id if chambre is not None else None
    )
    uh = (
        session.get(UniteHebergement, effective_uh_id)
        if effective_uh_id is not None
        else None
    )
    if uh_id is not None and uh is None:
        raise MovementCreationError("L'unité d'hébergement sélectionnée n'existe pas.")
    if (
        chambre is not None
        and uh is not None
        and chambre.unite_hebergement_id != uh.id
    ):
        raise MovementCreationError(
            "La chambre sélectionnée n'appartient pas à l'unité d'hébergement."
        )
    return uh, chambre, lit


def format_movement_location(
    uh: UniteHebergement | None,
    chambre: Chambre | None,
    lit: Lit | None,
) -> str | None:
    values = [
        entity.identifier
        for entity in (uh, chambre, lit)
        if entity is not None and entity.identifier
    ]
    return "^".join(values) if values else None


def create_patient_movement(
    session: Session,
    *,
    venue_id: int,
    type_code: str,
    when: datetime,
    uf_id: int | None = None,
    uf_soins_identifier: str | None = None,
    uh_id: int | None = None,
    chambre_id: int | None = None,
    lit_id: int | None = None,
    from_location: str | None = None,
    to_location: str | None = None,
    reason: str | None = None,
    movement_reason: str | None = None,
) -> Mouvement:
    """Valide le parcours, persiste le mouvement et actualise la venue."""

    venue = session.get(Venue, venue_id)
    if venue is None:
        raise MovementCreationError("La venue sélectionnée n'existe pas.", status_code=404)
    if venue.start_time and when < venue.start_time:
        raise MovementCreationError(
            "La date du mouvement ne peut pas être antérieure au début de la venue."
        )

    trigger_event = parse_movement_event(type_code)
    last_movement = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == venue_id)
        .order_by(Mouvement.when.desc(), Mouvement.id.desc())
    ).first()
    if last_movement is not None and when < last_movement.when:
        raise MovementCreationError(
            "La date du mouvement ne peut pas être antérieure au dernier mouvement."
        )

    last_event = None
    if last_movement is not None:
        last_event = last_movement.trigger_event or (
            last_movement.type.rsplit("^", 1)[-1] if last_movement.type else None
        )
    allowed_events = (
        ALLOWED_TRANSITIONS.get(last_event, set())
        if last_event
        else {event for event in INITIAL_EVENTS if event != "A38"}
    )
    if trigger_event not in allowed_events:
        raise MovementCreationError(
            f"L'événement {trigger_event} n'est pas autorisé dans l'état actuel."
        )

    uh, chambre, lit = load_movement_location(
        session,
        uh_id=uh_id,
        chambre_id=chambre_id,
        lit_id=lit_id,
    )
    requires_location = EVENT_METADATA.get(trigger_event, (None, False))[1]
    if requires_location and uh is None and chambre is None:
        raise MovementCreationError(
            "La localisation est obligatoire pour ce type de mouvement."
        )
    if trigger_event == "A02" and (uh is None or chambre is None or lit is None):
        raise MovementCreationError(
            "Pour un transfert (A02), l'UH, la chambre et le lit sont obligatoires."
        )

    uf = session.get(UniteFonctionnelle, uf_id) if uf_id is not None else None
    if uf_id is not None and uf is None:
        raise MovementCreationError("L'UF médicale sélectionnée n'existe pas.")
    uf_soins = None
    if uf_soins_identifier:
        uf_soins = session.exec(
            select(UniteFonctionnelle).where(
                UniteFonctionnelle.identifier == uf_soins_identifier
            )
        ).first()
        if uf_soins is None:
            raise MovementCreationError("L'UF de soins sélectionnée n'existe pas.")

    if uf is None and uh is not None and uh.unite_fonctionnelle_id:
        uf = session.get(UniteFonctionnelle, uh.unite_fonctionnelle_id)
    location = format_movement_location(uh, chambre, lit)
    movement_type = EVENT_METADATA.get(trigger_event, (None, False))[0]
    movement = Mouvement(
        mouvement_seq=get_next_sequence(session, "mouvement"),
        venue_id=venue_id,
        entite_juridique_id=venue.entite_juridique_id,
        type=type_code,
        trigger_event=trigger_event,
        movement_type=movement_type,
        when=when,
        location=location,
        from_location=(
            from_location
            if from_location is not None
            else (last_movement.location if last_movement else None)
        ),
        to_location=to_location if to_location is not None else location,
        reason=reason,
        movement_reason=movement_reason,
        uf_responsabilite=uf.identifier if uf else None,
        uf_soins_code=uf_soins.identifier if uf_soins else None,
        uf_soins_label=(
            (uf_soins.short_name or uf_soins.name) if uf_soins else None
        ),
    )
    if chambre is not None:
        venue.chambre_id = chambre.id
    if lit is not None:
        venue.lit_id = lit.id
    if location is not None:
        venue.assigned_location = location

    session.add(venue)
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return movement


__all__ = [
    "MovementCreationError",
    "create_patient_movement",
    "format_movement_location",
    "load_movement_location",
    "parse_movement_event",
]
