"""Préparation du formulaire de création d'un mouvement PAM."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.db import peek_next_sequence
from app.form_config import MouvementStatus, MovementType
from app.models import Dossier, Mouvement, Venue
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.movement_type_mapping import to_standard_movement_code
from app.services.vocabulary_lookup import get_vocabulary_options
from app.state_transitions import ALLOWED_TRANSITIONS, INITIAL_EVENTS


class MovementFormContextError(LookupError):
    """Erreur de contexte présentable directement par la route HTML."""

    def __init__(self, status_code: int, title: str, message: str, back_url: str):
        super().__init__(message)
        self.status_code = status_code
        self.title = title
        self.message = message
        self.back_url = back_url


@dataclass(frozen=True)
class MovementFormContext:
    title: str
    fields: list[dict[str, Any]]
    back_url: str


EVENT_METADATA = {
    "A01": ("admission", True),
    "A02": ("transfer", True),
    "A03": ("discharge", False),
    "A04": ("consultation_out", False),
    "A05": ("preadmission", False),
    "A06": ("class_change", True),
    "A07": ("from_consult", True),
    "A11": ("cancel_admission", False),
    "A12": ("cancel_transfer", False),
    "A13": ("cancel_discharge", False),
    "A21": ("temporary_leave", False),
    "A22": ("return", True),
    "A38": ("cancel_preadmission", False),
}

DOSSIER_TYPE_EVENTS = {
    "hospitalise": {"A01", "A02", "A03", "A06", "A11", "A12", "A13", "A21"},
    "externe": {"A04", "A07"},
    "urgence": {"A04", "A05", "A07", "A21"},
}


def _option(value: object, label: str | None) -> dict[str, str]:
    return {"value": str(value), "label": label or str(value)}


def _venue_options(venues: list[Venue]) -> list[dict[str, str]]:
    options = []
    for venue in venues:
        label = f"Venue #{venue.venue_seq}"
        if venue.dossier:
            if venue.dossier.patient:
                patient = venue.dossier.patient
                label += f" - {patient.family} {patient.given}"
            label += f" (Dossier #{venue.dossier.dossier_seq})"
        options.append(_option(venue.id, label))
    return options


def _load_venues(session: Session, dossier_id: int | None) -> list[Venue]:
    statement = select(Venue).options(
        selectinload(Venue.dossier).selectinload(Dossier.patient)
    )
    if dossier_id is not None:
        statement = statement.where(Venue.dossier_id == dossier_id)
    else:
        statement = statement.join(Dossier).where(
            Dossier.entite_juridique_id.is_not(None)
        )
    return list(session.exec(statement.order_by(Venue.venue_seq.asc())).all())


def _load_ufs(
    session: Session,
    *,
    ej_id: int | None,
    selected_identifier: str | None,
) -> list[UniteFonctionnelle]:
    ufs: list[UniteFonctionnelle] = []
    if ej_id is not None:
        ufs = list(
            session.exec(
                select(UniteFonctionnelle)
                .join(Service, UniteFonctionnelle.service_id == Service.id)
                .join(Pole, Service.pole_id == Pole.id)
                .outerjoin(
                    EntiteGeographique,
                    Pole.entite_geo_id == EntiteGeographique.id,
                )
                .where(
                    or_(
                        Pole.entite_juridique_id == ej_id,
                        EntiteGeographique.entite_juridique_id == ej_id,
                    )
                )
                .order_by(UniteFonctionnelle.name, UniteFonctionnelle.id)
            ).all()
        )

    if selected_identifier and not any(
        uf.identifier == selected_identifier for uf in ufs
    ):
        selected = session.exec(
            select(UniteFonctionnelle).where(
                UniteFonctionnelle.identifier == selected_identifier
            )
        ).first()
        if selected is not None:
            ufs.append(selected)

    if not ufs:
        ufs = list(
            session.exec(
                select(UniteFonctionnelle).order_by(
                    UniteFonctionnelle.name, UniteFonctionnelle.id
                )
            ).all()
        )

    # Un même rattachement peut satisfaire les deux branches du OR.
    return list({uf.id: uf for uf in ufs}.values())


def _find_location_selection(
    session: Session,
    location: str | None,
) -> tuple[UniteHebergement | None, Chambre | None, Lit | None]:
    if not location:
        return None, None, None

    parts = [part.strip() for part in location.split("^") if part.strip()]
    if len(parts) < 2:
        parts = [part.strip() for part in location.split("-") if part.strip()]
        # Compatibilité avec l'ancien format UF-UH-CHAMBRE-LIT.
        parts = parts[1:] if parts and parts[0] == "UF" else parts

    uh = None
    chambre = None
    lit = None
    if parts:
        uh_identifier = parts[0]
        uh = session.exec(
            select(UniteHebergement).where(
                or_(
                    UniteHebergement.identifier == uh_identifier,
                    UniteHebergement.identifier == f"UH-{uh_identifier}",
                )
            )
        ).first()
    if len(parts) >= 2:
        chambre = session.exec(
            select(Chambre).where(Chambre.identifier == parts[1])
        ).first()
    if len(parts) >= 3:
        lit = session.exec(select(Lit).where(Lit.identifier == parts[2])).first()
    return uh, chambre, lit


def _movement_type_options(
    dossier: Dossier | None,
    allowed_events: set[str],
) -> list[dict[str, Any]]:
    dossier_type = None
    if dossier is not None:
        dossier_type = getattr(dossier.dossier_type, "value", dossier.dossier_type)
    dossier_events = DOSSIER_TYPE_EVENTS.get(str(dossier_type))

    options = []
    for option in MovementType.choices():
        business_code = str(option["value"])
        hl7_code = to_standard_movement_code(business_code, "hl7")
        if not hl7_code:
            continue
        event = hl7_code.rsplit("^", 1)[-1]
        if event not in allowed_events:
            continue
        if dossier_events is not None and event not in dossier_events:
            continue
        options.append(
            {
                **option,
                "value": hl7_code,
                "requires_location": EVENT_METADATA.get(event, (None, False))[1],
            }
        )
    return options


def _selected_uf(
    session: Session,
    identifier: str | None,
) -> UniteFonctionnelle | None:
    if not identifier:
        return None
    return session.exec(
        select(UniteFonctionnelle).where(
            UniteFonctionnelle.identifier == identifier
        )
    ).first()


def build_new_movement_form(
    session: Session,
    *,
    venue_id: int | None,
    dossier_id: int | None,
    venue_context_id: int | None = None,
    dossier_context_id: int | None = None,
    now: datetime | None = None,
) -> MovementFormContext:
    """Charge le contexte et construit les champs du formulaire en une seule unité."""

    filter_dossier_id = dossier_id if dossier_id is not None else dossier_context_id
    venues = _load_venues(session, filter_dossier_id)

    if venue_id is not None and not any(venue.id == venue_id for venue in venues):
        requested = session.exec(
            select(Venue)
            .options(selectinload(Venue.dossier).selectinload(Dossier.patient))
            .where(Venue.id == venue_id)
        ).one_or_none()
        if requested is not None and (
            (filter_dossier_id is not None and requested.dossier_id == filter_dossier_id)
            or (
                filter_dossier_id is None
                and requested.dossier
                and requested.dossier.entite_juridique_id is not None
            )
        ):
            venues.append(requested)

    if not venues:
        raise MovementFormContextError(
            404,
            "Aucune venue disponible",
            "Impossible de créer un mouvement : aucune venue n'est disponible. "
            "Créez d'abord une venue.",
            "/venues/new" if filter_dossier_id else "/dossiers",
        )

    selected_venue_id = venue_id or venue_context_id or venues[0].id
    selected_venue = next(
        (venue for venue in venues if venue.id == selected_venue_id),
        venues[0],
    )
    selected_venue_id = selected_venue.id
    selected_dossier = selected_venue.dossier

    last_movement = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == selected_venue_id)
        .order_by(Mouvement.when.desc(), Mouvement.id.desc())
    ).first()

    uf_identifier = (
        last_movement.uf_responsabilite
        if last_movement and last_movement.uf_responsabilite
        else selected_venue.uf_responsabilite
        or (selected_dossier.uf_responsabilite if selected_dossier else None)
    )
    uf_soins_identifier = (
        last_movement.uf_soins_code
        if last_movement and last_movement.uf_soins_code
        else selected_venue.uf_soins_code
    )
    selected_uf = _selected_uf(session, uf_identifier)

    selected_uh, selected_chambre, selected_lit = _find_location_selection(
        session, last_movement.location if last_movement else None
    )
    if selected_chambre is None and selected_venue.chambre_id:
        selected_chambre = session.get(Chambre, selected_venue.chambre_id)
    if selected_lit is None and selected_venue.lit_id:
        selected_lit = session.get(Lit, selected_venue.lit_id)
    if selected_uh is None and selected_chambre is not None:
        selected_uh = session.get(
            UniteHebergement, selected_chambre.unite_hebergement_id
        )
    if selected_uh is None and selected_uf is not None:
        selected_uh = session.exec(
            select(UniteHebergement)
            .where(UniteHebergement.unite_fonctionnelle_id == selected_uf.id)
            .order_by(UniteHebergement.name, UniteHebergement.id)
        ).first()

    ej_id = selected_dossier.entite_juridique_id if selected_dossier else None
    ufs = _load_ufs(session, ej_id=ej_id, selected_identifier=uf_identifier)
    uf_options = [
        _option(uf.id, uf.short_name.strip() if uf.short_name and uf.short_name.strip() else uf.name)
        for uf in ufs
    ]
    uf_soins_options = [
        _option(uf.identifier, uf.short_name.strip() if uf.short_name and uf.short_name.strip() else uf.name)
        for uf in ufs
        if uf.identifier
    ]

    if selected_uf is not None:
        uhs = list(
            session.exec(
                select(UniteHebergement)
                .where(UniteHebergement.unite_fonctionnelle_id == selected_uf.id)
                .order_by(UniteHebergement.name, UniteHebergement.id)
            ).all()
        )
    else:
        uhs = list(
            session.exec(
                select(UniteHebergement).order_by(
                    UniteHebergement.name, UniteHebergement.id
                )
            ).all()
        )
    if selected_uh is not None and not any(uh.id == selected_uh.id for uh in uhs):
        uhs.append(selected_uh)

    chambres = (
        list(
            session.exec(
                select(Chambre)
                .where(Chambre.unite_hebergement_id == selected_uh.id)
                .order_by(Chambre.name, Chambre.id)
            ).all()
        )
        if selected_uh is not None
        else []
    )
    lits = (
        list(
            session.exec(
                select(Lit)
                .where(Lit.chambre_id == selected_chambre.id)
                .order_by(Lit.name, Lit.id)
            ).all()
        )
        if selected_chambre is not None
        else []
    )

    clock = now or datetime.now()
    if last_movement is not None:
        last_event = (
            last_movement.trigger_event
            or (last_movement.type.rsplit("^", 1)[-1] if last_movement.type else None)
        )
        allowed_events = ALLOWED_TRANSITIONS.get(last_event, set())
        default_when = last_movement.when + timedelta(minutes=1)
    else:
        allowed_events = {event for event in INITIAL_EVENTS if event != "A38"}
        default_when = clock

    reason_options = get_vocabulary_options("movement-reason")
    fields = [
        {
            "label": "Venue (Séjour) *",
            "name": "venue_id",
            "type": "select",
            "options": _venue_options(venues),
            "value": str(selected_venue_id),
            "required": True,
            "help": "Sélectionnez la venue concernée par ce mouvement",
        },
        {
            "label": "Type de mouvement *",
            "name": "type",
            "type": "select",
            "options": _movement_type_options(selected_dossier, allowed_events),
            "required": True,
            "help": "Options filtrées selon l'état actuel de la venue et le type de séjour",
        },
        {
            "label": "Date et heure *",
            "name": "when",
            "type": "datetime-local",
            "value": default_when.strftime("%Y-%m-%dT%H:%M"),
            "required": True,
            "help": "Date et heure du mouvement",
        },
        {
            "label": "Unité médicale (UF)",
            "name": "uf_id",
            "type": "select",
            "options": uf_options,
            "value": str(selected_uf.id) if selected_uf else None,
            "help": "Sélectionnez l'UF médicale concernée",
            "empty_message": "Aucune UF disponible pour l'établissement sélectionné.",
        },
        {
            "label": "Unité de Soins (UF Soins)",
            "name": "uf_soins_id",
            "type": "select",
            "options": uf_soins_options,
            "value": uf_soins_identifier,
            "help": "Sélectionnez l'unité de soins",
            "empty_message": "Aucune UF disponible pour l'établissement sélectionné.",
        },
        {
            "label": "Unité d'Hébergement (UH)",
            "name": "uh_id",
            "type": "select",
            "options": [_option(uh.id, f"{uh.identifier} — {uh.name}") for uh in uhs],
            "value": str(selected_uh.id) if selected_uh else None,
            "help": "Sélectionnez l'unité d'hébergement liée à l'UF",
            "parent_field": "uf_soins_id",
            "depends_on": "une UF de Soins",
            "empty_message": "Sélectionnez d'abord une UF de Soins.",
        },
        {
            "label": "Chambre (optionnel)",
            "name": "chambre_id",
            "type": "select",
            "options": [
                _option(chambre.id, f"{chambre.identifier} — {chambre.name}")
                for chambre in chambres
            ],
            "value": str(selected_chambre.id) if selected_chambre else None,
            "help": "Optionnel - Requis uniquement pour hospitalisation confirmée",
            "parent_field": "uh_id",
            "depends_on": "une UH (Unité d'Hébergement)",
            "empty_message": "Sélectionnez d'abord une UH.",
        },
        {
            "label": "Lit (optionnel)",
            "name": "lit_id",
            "type": "select",
            "options": [_option(lit.id, f"{lit.identifier} — {lit.name}") for lit in lits],
            "value": str(selected_lit.id) if selected_lit else None,
            "help": "Optionnel - Requis uniquement avec une chambre assignée",
            "parent_field": "chambre_id",
            "depends_on": "une Chambre",
            "empty_message": "Sélectionnez d'abord une chambre.",
        },
        {
            "label": "Depuis (départ)",
            "name": "from_location",
            "type": "text",
            "value": last_movement.from_location if last_movement else None,
            "help": "Pour les transferts : lieu de départ",
        },
        {
            "label": "Vers (arrivée)",
            "name": "to_location",
            "type": "text",
            "value": last_movement.to_location if last_movement else None,
            "help": "Pour les transferts : lieu d'arrivée",
        },
        {
            "label": "Raison / Motif",
            "name": "reason",
            "type": "select" if reason_options else "text",
            "options": reason_options,
            "value": last_movement.reason if last_movement else None,
            "help": "Motif du mouvement",
        },
        {
            "label": "Numéro de séquence",
            "name": "mouvement_seq",
            "type": "number",
            "value": peek_next_sequence(session, "mouvement"),
            "readonly": True,
            "help": "Généré automatiquement",
        },
        {
            "label": "Statut du mouvement",
            "name": "status",
            "type": "select",
            "options": MouvementStatus.choices(),
            "value": "pending",
            "readonly": True,
            "hidden": True,
            "help": "Indicateur interne, non modifiable.",
        },
    ]

    title = "Nouveau mouvement"
    if filter_dossier_id is not None:
        dossier = next(
            (venue.dossier for venue in venues if venue.dossier_id == filter_dossier_id),
            None,
        )
        if dossier is not None:
            title += f" pour le dossier #{dossier.dossier_seq}"
    return MovementFormContext(
        title=title,
        fields=fields,
        back_url=(
            f"/mouvements?dossier_id={filter_dossier_id}"
            if filter_dossier_id is not None
            else "/venues"
        ),
    )


__all__ = [
    "MovementFormContext",
    "MovementFormContextError",
    "build_new_movement_form",
]
