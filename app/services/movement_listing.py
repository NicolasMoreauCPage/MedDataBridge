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


def movement_status_badge(status: str | None) -> str:
    colors = {
        "active": "bg-green-100 text-green-800",
        "completed": "bg-blue-100 text-blue-800",
        "cancelled": "bg-red-100 text-red-800",
        "pending": "bg-yellow-100 text-yellow-800",
    }
    value = status or "inconnu"
    class_name = colors.get(value, "bg-slate-100 text-slate-800")
    return (
        '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full '
        f'text-xs font-medium {class_name}">{value.title()}</span>'
    )


def movement_type_badge(movement_type: str | None) -> str:
    if not movement_type:
        return "—"
    colors = {
        "admission": "bg-blue-100 text-blue-800",
        "registration": "bg-indigo-100 text-indigo-800",
        "preadmission": "bg-sky-100 text-sky-800",
        "class-change": "bg-violet-100 text-violet-800",
        "transfer": "bg-amber-100 text-amber-800",
        "transfer-cancel": "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
        "discharge": "bg-red-100 text-red-800",
        "discharge-cancel": "bg-orange-100 text-orange-800",
        "leave-out": "bg-yellow-100 text-yellow-800",
        "leave-return": "bg-green-100 text-green-800",
        "doctor-change": "bg-teal-100 text-teal-800",
        "doctor-change-cancel": "bg-teal-50 text-teal-700 ring-1 ring-teal-200",
        "update": "bg-slate-100 text-slate-800",
    }
    labels = {
        "admission": "Admission",
        "registration": "Consultation",
        "preadmission": "Pré-admission",
        "class-change": "Mutation",
        "transfer": "Transfert",
        "transfer-cancel": "Annul. transfert",
        "discharge": "Sortie",
        "discharge-cancel": "Annul. sortie",
        "leave-out": "Permission",
        "leave-return": "Retour perm.",
        "doctor-change": "Change. médecin",
        "doctor-change-cancel": "Annul. médecin",
        "update": "MàJ identité",
    }
    class_name = colors.get(movement_type, "bg-slate-100 text-slate-800")
    label = labels.get(movement_type, movement_type.title())
    return (
        '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full '
        f'text-xs font-medium {class_name}">{label}</span>'
    )


def _movement_row(movement: Mouvement) -> dict:
    type_cell = movement_type_badge(movement.movement_type)
    if movement.cancelled_movement_seq:
        type_cell += (
            "<span class='ml-2 text-xs text-slate-500'>"
            f"(annule #{movement.cancelled_movement_seq})</span>"
        )
    return {
        "cells": [
            movement.mouvement_seq,
            movement.id,
            movement.venue_id,
            type_cell,
            movement_status_badge(movement.status or "pending"),
            movement.when.strftime("%d/%m/%Y %H:%M") if movement.when else None,
            movement.location,
            movement.performer,
        ],
        "detail_url": f"/mouvements/{movement.id}",
        "edit_url": f"/mouvements/{movement.id}/edit",
        "delete_url": f"/mouvements/{movement.id}/delete",
    }


def build_movement_list_view(
    result: MovementListResult,
    *,
    venue_id: int | None,
    dossier_id: int | None,
    include_cancelled: bool,
    order: str,
    movement_type: str | None,
    status: str | None,
    location_filter: str | None,
) -> dict:
    """Projette les données chargées vers le contrat du template de liste."""

    venue = result.venue
    dossier = result.dossier
    breadcrumbs = [{"label": "Mouvements", "url": "#"}]
    if venue_id is not None and venue is not None:
        breadcrumbs.insert(
            0, {"label": f"Venue #{venue.venue_seq}", "url": f"/venues/{venue_id}"}
        )
        if venue.dossier:
            breadcrumbs.insert(
                0,
                {
                    "label": f"Dossier #{venue.dossier.dossier_seq}",
                    "url": f"/dossiers/{venue.dossier.id}",
                },
            )
            if venue.dossier.patient:
                patient = venue.dossier.patient
                breadcrumbs.insert(
                    0,
                    {
                        "label": f"Patient: {patient.family} {patient.given}",
                        "url": f"/patients/{patient.id}",
                    },
                )
    elif dossier_id is not None and dossier is not None:
        breadcrumbs.insert(
            0,
            {
                "label": f"Dossier #{dossier.dossier_seq}",
                "url": f"/dossiers/{dossier.id}",
            },
        )
        if dossier.patient:
            breadcrumbs.insert(
                0,
                {
                    "label": f"Patient: {dossier.patient.family} {dossier.patient.given}",
                    "url": f"/patients/{dossier.patient.id}",
                },
            )

    filters = [
        {
            "label": "Type",
            "name": "type",
            "type": "select",
            "placeholder": "Tous les types",
            "value": movement_type or "",
            "options": [
                {"value": "ADT^A01", "label": "Admission"},
                {"value": "ADT^A02", "label": "Transfert"},
                {"value": "ADT^A03", "label": "Sortie"},
                {"value": "ADT^A04", "label": "Urgences / consultation externe"},
            ],
        },
        {
            "label": "Statut",
            "name": "status",
            "type": "select",
            "placeholder": "Tous les statuts",
            "value": status or "",
            "options": [
                {"value": "pending", "label": "En attente"},
                {"value": "active", "label": "En cours"},
                {"value": "completed", "label": "Terminé"},
                {"value": "cancelled", "label": "Annulé"},
            ],
        },
        {
            "label": "Localisation",
            "name": "location",
            "type": "text",
            "placeholder": "Filtrer par localisation",
            "value": location_filter or "",
        },
    ]

    context_query = (
        f"venue_id={venue_id}"
        if venue_id is not None
        else (f"dossier_id={dossier_id}" if dossier_id is not None else "")
    )
    actions = []
    if context_query:
        actions.extend(
            [
                {
                    "type": "link",
                    "label": "Vue état actuel",
                    "url": f"/mouvements/etat?{context_query}",
                },
                {
                    "type": "link",
                    "label": "Vue historique",
                    "url": f"/mouvements/historique?{context_query}",
                },
            ]
        )
    actions.extend(
        [
            {"type": "link", "label": "Export FHIR", "url": "/mouvements/export/fhir"},
            {"type": "link", "label": "Export HL7", "url": "/mouvements/export/hl7"},
        ]
    )
    if context_query:
        actions.insert(
            0,
            {
                "type": "link",
                "label": "Masquer les annulés" if include_cancelled else "Afficher les annulés",
                "url": (
                    f"/mouvements?{context_query}&include_cancelled="
                    f"{0 if include_cancelled else 1}&order={order}"
                ),
            },
        )
        reverse_order = "desc" if order == "asc" else "asc"
        reverse_label = (
            "Trier: plus récent → plus ancien"
            if order == "asc"
            else "Trier: plus ancien → plus récent"
        )
        actions.insert(
            0,
            {
                "type": "link",
                "label": reverse_label,
                "url": (
                    f"/mouvements?{context_query}&include_cancelled="
                    f"{'1' if include_cancelled else '0'}&order={reverse_order}"
                ),
            },
        )

    base = ""
    if venue_id is not None and venue is not None:
        base = f"de la venue #{venue.venue_seq}"
    elif dossier_id is not None and dossier is not None:
        base = f"du dossier #{dossier.dossier_seq}"
    title_prefix = "Historique des mouvements" if include_cancelled else "Mouvements (état actuel)"
    tabs = (
        [
            {
                "label": "État actuel",
                "url": f"/mouvements/etat?{context_query}",
                "active": not include_cancelled,
            },
            {
                "label": "Historique",
                "url": f"/mouvements/historique?{context_query}",
                "active": include_cancelled,
            },
        ]
        if context_query
        else None
    )
    new_url = "/mouvements/new"
    if venue_id is not None:
        new_url += f"?venue_id={venue_id}"
    elif dossier_id is not None:
        new_url += f"?dossier_id={dossier_id}"
    return {
        "title": f"{title_prefix} {base}".strip(),
        "breadcrumbs": breadcrumbs,
        "tabs": tabs,
        "headers": [
            "Seq",
            "ID",
            "Venue",
            "Type",
            "Status",
            "Date/Heure",
            "Localisation",
            "Intervenant",
        ],
        "rows": [_movement_row(movement) for movement in result.movements],
        "context": {
            "venue_id": venue_id,
            "include_cancelled": include_cancelled,
            "order": order,
        },
        "new_url": new_url,
        "filters": filters,
        "actions": actions,
        "show_actions": True,
    }


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


__all__ = [
    "MovementListContextError",
    "MovementListResult",
    "build_movement_list_view",
    "load_movement_list",
    "movement_status_badge",
    "movement_type_badge",
]
