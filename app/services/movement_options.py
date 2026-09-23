"""Options dynamiques utilisées par les formulaires de mouvement."""

from sqlmodel import Session, select

from app.models_structure import Chambre, Lit, UniteFonctionnelle, UniteHebergement
from app.services.vocabulary_lookup import get_vocabulary_options


class MovementOptionParentNotFound(LookupError):
    """Le parent demandé pour une liste dépendante n'existe pas."""


REASONS_BY_EVENT = {
    "A01": {"urgence", "programmee", "transfert_entrant", "naissance"},
    "A02": {"transfert_interne", "mutation_service", "changement_lit"},
    "A03": {"guerison", "transfert_sortant", "deces", "contre_avis", "domicile"},
    "A04": {"consultation", "visite"},
    "A05": {"preadmission", "programmation"},
    "A06": {"mutation", "reclassement"},
    "A07": {"retour_consultation"},
    "A08": {"erreur"},
    "A11": {"annulation_admission"},
    "A12": {"annulation_transfert"},
    "A13": {"annulation_sortie"},
    "A21": {"permission_sortie"},
    "A22": {"retour_permission"},
    "A38": {"annulation_preadmission"},
}


def room_options(session: Session, uh_id: int) -> list[dict[str, str]]:
    rooms = session.exec(
        select(Chambre)
        .where(Chambre.unite_hebergement_id == uh_id)
        .order_by(Chambre.name, Chambre.id)
    ).all()
    return [
        {"value": str(room.id), "label": room.name or room.identifier or str(room.id)}
        for room in rooms
    ]


def accommodation_options(
    session: Session,
    uf_identifier: str,
) -> list[dict[str, str]]:
    uf = session.exec(
        select(UniteFonctionnelle).where(
            UniteFonctionnelle.identifier == uf_identifier
        )
    ).first()
    if uf is None:
        raise MovementOptionParentNotFound(
            f"UF avec l'identifiant {uf_identifier} introuvable"
        )
    accommodations = session.exec(
        select(UniteHebergement)
        .where(UniteHebergement.unite_fonctionnelle_id == uf.id)
        .order_by(UniteHebergement.name, UniteHebergement.id)
    ).all()
    return [
        {
            "value": str(accommodation.id),
            "label": accommodation.name or accommodation.identifier or str(accommodation.id),
        }
        for accommodation in accommodations
    ]


def bed_options(session: Session, room_id: int) -> list[dict[str, str]]:
    beds = session.exec(
        select(Lit).where(Lit.chambre_id == room_id).order_by(Lit.name, Lit.id)
    ).all()
    return [
        {"value": str(bed.id), "label": bed.name or bed.identifier or str(bed.id)}
        for bed in beds
    ]


def movement_reason_options(movement_type: str) -> list[dict[str, str]]:
    options = get_vocabulary_options("movement-reason") or []
    event = movement_type.rsplit("^", 1)[-1]
    allowed = REASONS_BY_EVENT.get(event)
    if allowed is None:
        return options
    return [option for option in options if option.get("value") in allowed]


__all__ = [
    "MovementOptionParentNotFound",
    "accommodation_options",
    "bed_options",
    "movement_reason_options",
    "room_options",
]
