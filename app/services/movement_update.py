"""Cas d'usage transactionnel de modification d'un mouvement patient."""

from datetime import datetime

from sqlmodel import Session, select

from app.models import Mouvement, Venue
from app.models_structure import UniteFonctionnelle
from app.services.movement_creation import (
    MovementCreationError,
    format_movement_location,
    load_movement_location,
    parse_movement_event,
)
from app.services.movement_form_context import EVENT_METADATA
from app.workflows.transitions import ALLOWED_TRANSITIONS, INITIAL_EVENTS


def update_patient_movement(
    session: Session,
    *,
    movement_id: int,
    venue_id: int,
    type_code: str,
    when: datetime,
    uf_identifier: str | None = None,
    uf_soins_identifier: str | None = None,
    uh_id: int | None = None,
    chambre_id: int | None = None,
    lit_id: int | None = None,
    from_location: str | None = None,
    to_location: str | None = None,
    reason: str | None = None,
    movement_reason: str | None = None,
) -> Mouvement:
    """Valide puis met à jour un mouvement sans dupliquer les règles de création."""

    movement = session.get(Mouvement, movement_id)
    if movement is None:
        raise MovementCreationError("Mouvement introuvable.", status_code=404)
    venue = session.get(Venue, venue_id)
    if venue is None:
        raise MovementCreationError("La venue sélectionnée n'existe pas.", status_code=404)
    if venue.start_time and when < venue.start_time:
        raise MovementCreationError(
            "La date du mouvement ne peut pas être antérieure au début de la venue."
        )

    trigger_event = parse_movement_event(type_code)
    previous = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == venue_id, Mouvement.id != movement_id)
        .where(Mouvement.when <= when)
        .order_by(Mouvement.when.desc(), Mouvement.id.desc())
    ).first()
    previous_event = None
    if previous is not None:
        previous_event = previous.trigger_event or (
            previous.type.rsplit("^", 1)[-1] if previous.type else None
        )
    allowed_events = (
        ALLOWED_TRANSITIONS.get(previous_event, set())
        if previous_event
        else {event for event in INITIAL_EVENTS if event != "A38"}
    )
    if trigger_event not in allowed_events and trigger_event != movement.trigger_event:
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

    uf = None
    if uf_identifier:
        uf = session.exec(
            select(UniteFonctionnelle).where(
                UniteFonctionnelle.identifier == uf_identifier
            )
        ).first()
        if uf is None:
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
    movement.venue_id = venue_id
    movement.type = type_code
    movement.trigger_event = trigger_event
    movement.movement_type = EVENT_METADATA.get(trigger_event, (None, False))[0]
    movement.when = when
    movement.location = location
    movement.from_location = from_location
    movement.to_location = to_location if to_location is not None else location
    movement.reason = reason
    movement.movement_reason = movement_reason
    movement.uf_responsabilite = uf.identifier if uf else None
    movement.uf_soins_code = uf_soins.identifier if uf_soins else None
    movement.uf_soins_label = (
        (uf_soins.short_name or uf_soins.name) if uf_soins else None
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


__all__ = ["update_patient_movement"]
