"""Lecture optimisée et projection du plan de lits."""

from collections import defaultdict
from typing import Any

from sqlmodel import Session, select

from app.models import Dossier, Mouvement, Patient, Venue
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)


def _locations_query(
    *,
    eg_ids: list[int] | None,
    ej_id: int | None,
    uf_filter: str | None,
    service_filter: str | None,
    entity_type: str | None,
    entity_id: int | None,
):
    query = (
        select(Lit, Chambre, UniteHebergement, UniteFonctionnelle, Service)
        .select_from(Lit)
        .join(Lit.chambre)
        .join(Chambre.unite_hebergement)
        .join(UniteHebergement.unite_fonctionnelle)
        .join(UniteFonctionnelle.service)
        .join(Service.pole)
    )
    if eg_ids:
        query = query.where(Pole.entite_geo_id.in_(eg_ids))
    elif ej_id:
        query = query.where(Pole.entite_juridique_id == ej_id)
    if uf_filter:
        query = query.where(UniteFonctionnelle.identifier == uf_filter)
    if service_filter:
        query = query.where(Service.name.ilike(f"%{service_filter}%"))
    if entity_type and entity_id:
        entity_filters = {
            "eg": Pole.entite_geo_id == entity_id,
            "pole": Service.pole_id == entity_id,
            "service": UniteFonctionnelle.service_id == entity_id,
            "uf": UniteHebergement.unite_fonctionnelle_id == entity_id,
            "uh": Chambre.unite_hebergement_id == entity_id,
            "chambre": Lit.chambre_id == entity_id,
            "lit": Lit.id == entity_id,
        }
        condition = entity_filters.get(entity_type)
        if condition is not None:
            query = query.where(condition)
    return query


def _load_locations(
    session: Session,
    *,
    eg_id: int | None,
    ej_id: int | None,
    ej_from_eg_id: int | None,
    uf_filter: str | None,
    service_filter: str | None,
    entity_type: str | None,
    entity_id: int | None,
):
    def execute(filter_eg_ids=None, filter_ej_id=None):
        return session.exec(
            _locations_query(
                eg_ids=filter_eg_ids,
                ej_id=filter_ej_id,
                uf_filter=uf_filter,
                service_filter=service_filter,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        ).all()

    if entity_type and entity_id:
        locations = execute()
    elif eg_id:
        locations = execute(filter_eg_ids=[eg_id])
    elif ej_id:
        locations = execute(filter_ej_id=ej_id)
    else:
        locations = execute()

    if not locations and eg_id and ej_from_eg_id:
        locations = execute(filter_ej_id=ej_from_eg_id)
    if not locations and ej_id:
        fallback_eg_ids = session.exec(
            select(EntiteGeographique.id).where(
                EntiteGeographique.entite_juridique_id == ej_id
            )
        ).all()
        if fallback_eg_ids:
            locations = execute(filter_eg_ids=list(fallback_eg_ids))
    return locations


def _is_active(latest: Mouvement | None) -> bool:
    if latest is None:
        return True
    is_discharge = (latest.trigger_event or "") == "A03" or "A03" in (latest.type or "")
    return not (is_discharge and latest.end_time)


def _active_venues_by_bed(
    session: Session,
    bed_ids: list[int],
) -> dict[int, list[tuple[Venue, Dossier, Patient]]]:
    if not bed_ids:
        return {}
    rows = session.exec(
        select(Venue, Dossier, Patient)
        .join(Dossier, Dossier.id == Venue.dossier_id)
        .join(Patient, Patient.id == Dossier.patient_id)
        .where(Venue.lit_id.in_(bed_ids))
        .order_by(Venue.start_time.desc(), Venue.id.desc())
    ).all()
    venue_ids = [venue.id for venue, _dossier, _patient in rows if venue.id is not None]
    movements = (
        session.exec(
            select(Mouvement)
            .where(Mouvement.venue_id.in_(venue_ids))
            .order_by(Mouvement.venue_id, Mouvement.when.desc(), Mouvement.id.desc())
        ).all()
        if venue_ids
        else []
    )
    latest_by_venue: dict[int, Mouvement] = {}
    for movement in movements:
        latest_by_venue.setdefault(movement.venue_id, movement)

    active: dict[int, list[tuple[Venue, Dossier, Patient]]] = defaultdict(list)
    for venue, dossier, patient in rows:
        if venue.lit_id is not None and _is_active(latest_by_venue.get(venue.id)):
            active[venue.lit_id].append((venue, dossier, patient))
    return dict(active)


def _empty_structure_node(
    structure: dict[int, dict[str, Any]],
    *,
    service: Service,
    uf: UniteFonctionnelle,
    uh: UniteHebergement,
    chambre: Chambre,
) -> list[dict[str, Any]]:
    service_node = structure.setdefault(
        service.id,
        {
            "id": service.id,
            "name": service.name,
            "service_type": service.service_type,
            "ufs": {},
        },
    )
    uf_node = service_node["ufs"].setdefault(
        uf.id,
        {"id": uf.id, "name": uf.name, "identifier": uf.identifier, "uhs": {}},
    )
    uh_node = uf_node["uhs"].setdefault(
        uh.id,
        {
            "id": uh.id,
            "name": uh.name,
            "identifier": uh.identifier,
            "chambres": {},
        },
    )
    chambre_node = uh_node["chambres"].setdefault(
        chambre.id,
        {
            "id": chambre.id,
            "name": chambre.name,
            "identifier": chambre.identifier,
            "lits": [],
        },
    )
    return chambre_node["lits"]


def _display_status(bed: Lit, occupied: bool) -> str:
    if occupied:
        return "occupied"
    operational_status = (bed.operational_status or "").lower()
    if operational_status in {"available", ""}:
        return "free"
    if operational_status in {"maintenance", "closed"}:
        return "closed"
    if operational_status == "occupied":
        return "occupied"
    return "unknown"


def build_bed_plan(
    session: Session,
    *,
    eg_id: int | None = None,
    ej_id: int | None = None,
    ej_from_eg_id: int | None = None,
    uf_filter: str | None = None,
    service_filter: str | None = None,
    status_filter: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> dict[str, Any]:
    """Charge le plan et ses occupants avec un nombre constant de requêtes."""

    locations = _load_locations(
        session,
        eg_id=eg_id,
        ej_id=ej_id,
        ej_from_eg_id=ej_from_eg_id,
        uf_filter=uf_filter,
        service_filter=service_filter,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    bed_ids = [bed.id for bed, *_rest in locations if bed.id is not None]
    active_venues = _active_venues_by_bed(session, bed_ids)
    structure: dict[int, dict[str, Any]] = {}

    for bed, chambre, uh, uf, service in locations:
        bed_rows = _empty_structure_node(
            structure,
            service=service,
            uf=uf,
            uh=uh,
            chambre=chambre,
        )
        occupants = active_venues.get(bed.id, [])
        display_status = _display_status(bed, bool(occupants))
        if status_filter and display_status != status_filter:
            continue
        occupant = None
        if occupants:
            venue, dossier, patient = occupants[0]
            occupant = {
                "venue_id": venue.id,
                "dossier_id": dossier.id,
                "patient_name": f"{patient.family} {patient.given}",
                "patient_id": patient.id,
                "venue_seq": venue.venue_seq,
                "dossier_seq": dossier.dossier_seq,
            }
        bed_rows.append(
            {
                "id": bed.id,
                "name": bed.name,
                "identifier": bed.identifier,
                "status": display_status,
                "operational_status": bed.operational_status,
                "occupant": occupant,
                "has_conflict": len(occupants) > 1,
                "conflict_count": len(occupants) if len(occupants) > 1 else 0,
            }
        )

    beds = [
        bed
        for service in structure.values()
        for uf in service["ufs"].values()
        for uh in uf["uhs"].values()
        for chambre in uh["chambres"].values()
        for bed in chambre["lits"]
    ]
    occupied = sum(bed["status"] == "occupied" for bed in beds)
    ufs = session.exec(select(UniteFonctionnelle).order_by(UniteFonctionnelle.name)).all()
    services = session.exec(select(Service).order_by(Service.name)).all()
    return {
        "structure": structure,
        "stats": {
            "total": len(beds),
            "libres": sum(bed["status"] == "free" for bed in beds),
            "occupes": occupied,
            "taux_occupation": round((occupied / len(beds) * 100) if beds else 0, 1),
        },
        "filters": {"uf": uf_filter, "service": service_filter, "status": status_filter},
        "uf_options": [{"value": uf.identifier, "label": uf.name} for uf in ufs],
        "service_options": [
            {"value": service.name, "label": service.name} for service in services
        ],
    }


__all__ = ["build_bed_plan"]
