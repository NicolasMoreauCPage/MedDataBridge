"""Affectation transactionnelle d'une venue active à un lit."""

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.db import get_next_sequence
from app.models import Dossier, Mouvement, Patient, Venue
from app.models_structure import Lit


class BedAssignmentError(ValueError):
    """Erreur métier présentable à l'utilisateur du plan de lits."""


@dataclass(frozen=True)
class BedAssignmentResult:
    message: str
    movement: Mouvement | None


def _latest_movements(
    session: Session,
    venue_ids: set[int],
) -> dict[int, Mouvement]:
    if not venue_ids:
        return {}
    movements = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id.in_(venue_ids))
        .order_by(Mouvement.venue_id, Mouvement.when.desc(), Mouvement.id.desc())
    ).all()
    latest: dict[int, Mouvement] = {}
    for movement in movements:
        latest.setdefault(movement.venue_id, movement)
    return latest


def _is_active(venue: Venue, latest_movements: dict[int, Mouvement]) -> bool:
    latest = latest_movements.get(venue.id)
    if latest is None:
        return True
    is_discharge = (latest.trigger_event or "") == "A03" or "A03" in (latest.type or "")
    return not (is_discharge and latest.end_time)


def assign_patient_to_bed(
    session: Session,
    *,
    bed_id: int,
    patient_id: int,
) -> BedAssignmentResult:
    """Affecte la dernière venue active et crée la trace de transfert A02."""

    bed = session.get(Lit, bed_id)
    patient = session.get(Patient, patient_id)
    if bed is None or patient is None:
        raise BedAssignmentError("Lit ou patient introuvable.")

    patient_venues = session.exec(
        select(Venue)
        .join(Dossier)
        .where(Dossier.patient_id == patient.id)
        .order_by(Venue.start_time.desc(), Venue.id.desc())
    ).all()
    bed_venues = session.exec(select(Venue).where(Venue.lit_id == bed.id)).all()
    venue_ids = {
        venue.id
        for venue in (*patient_venues, *bed_venues)
        if venue.id is not None
    }
    latest_movements = _latest_movements(session, venue_ids)
    venue = next(
        (
            candidate
            for candidate in patient_venues
            if _is_active(candidate, latest_movements)
        ),
        None,
    )
    if venue is None:
        raise BedAssignmentError("Ce patient n'a pas de venue active à affecter.")
    if any(
        candidate.id != venue.id and _is_active(candidate, latest_movements)
        for candidate in bed_venues
    ):
        raise BedAssignmentError(
            "Ce lit est déjà occupé. Actualisez le plan avant de recommencer."
        )
    if venue.lit_id == bed.id:
        return BedAssignmentResult("Le patient occupe déjà ce lit.", None)

    previous_location = venue.assigned_location
    venue.lit_id = bed.id
    venue.chambre_id = bed.chambre_id
    venue.assigned_location = bed.name
    movement = Mouvement(
        mouvement_seq=get_next_sequence(session, "mouvement"),
        venue_id=venue.id,
        entite_juridique_id=venue.entite_juridique_id,
        type="ADT^A02",
        trigger_event="A02",
        movement_type="transfer",
        when=datetime.utcnow(),
        from_location=previous_location,
        to_location=bed.name,
        location=bed.name,
        status="completed",
        action="UPDATE",
    )
    session.add(venue)
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return BedAssignmentResult(
        f"{patient.family} {patient.given} a été affecté au lit {bed.name}.",
        movement,
    )


__all__ = ["BedAssignmentError", "BedAssignmentResult", "assign_patient_to_bed"]
