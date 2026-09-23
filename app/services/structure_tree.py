"""Chargement et projection de l'arbre de structure hospitalière."""

from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models_structure import (
    Chambre,
    EntiteGeographique,
    Lit,
    LocationStatus,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.structure_schedule import apply_scheduled_status


def build_structure_tree_for_template(
    session: Session,
    eg: EntiteGeographique,
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    """Projette les relations déjà chargées pour les templates de détail EG."""

    structure_tree = []
    lit_operational: dict[str, int] = {}
    lits_actifs = 0

    for pole in getattr(eg, "poles", []) or []:
        pole_node = {"entity": pole, "services": []}
        for service in getattr(pole, "services", []) or []:
            service_node = {"entity": service, "ufs": []}
            for uf in getattr(service, "unites_fonctionnelles", []) or []:
                uf_node = {"entity": uf, "uhs": []}
                for uh in getattr(uf, "unites_hebergement", []) or []:
                    uh_node = {"entity": uh, "chambres": []}
                    for chambre in getattr(uh, "chambres", []) or []:
                        chambre_node = {"entity": chambre, "lits": []}
                        for lit in getattr(chambre, "lits", []) or []:
                            chambre_node["lits"].append(
                                {
                                    "id": lit.id,
                                    "name": lit.name,
                                    "identifier": getattr(lit, "identifier", None),
                                }
                            )
                            operational_status = getattr(lit, "operational_status", None) or "unknown"
                            lit_operational[operational_status] = (
                                lit_operational.get(operational_status, 0) + 1
                            )
                            if getattr(lit, "status", None) == LocationStatus.ACTIVE:
                                lits_actifs += 1
                        uh_node["chambres"].append(chambre_node)
                    uf_node["uhs"].append(uh_node)
                service_node["ufs"].append(uf_node)
            pole_node["services"].append(service_node)
        structure_tree.append(pole_node)

    return structure_tree, lit_operational, lits_actifs


def _effective_status(entity: Any) -> str:
    resolver = getattr(entity, "get_effective_status", None)
    status = resolver() if callable(resolver) else getattr(entity, "status", None)
    if isinstance(status, LocationStatus):
        return status.value
    return status or "active"


def _lit_node(lit: Lit) -> dict[str, Any]:
    return {
        "id": lit.id,
        "name": lit.name,
        "type": "lit",
        "status": _effective_status(lit),
    }


def _chambre_node(chambre: Chambre) -> dict[str, Any]:
    return {
        "id": chambre.id,
        "name": chambre.name,
        "type": "chambre",
        "status": _effective_status(chambre),
        "lits": [_lit_node(lit) for lit in chambre.lits],
    }


def _uh_node(uh: UniteHebergement) -> dict[str, Any]:
    return {
        "id": uh.id,
        "name": uh.name,
        "type": "uh",
        "status": _effective_status(uh),
        "chambres": [_chambre_node(chambre) for chambre in uh.chambres],
        "lits": [],
    }


def _uf_node(uf: UniteFonctionnelle) -> dict[str, Any]:
    return {
        "id": uf.id,
        "name": uf.name,
        "type": "uf",
        "status": _effective_status(uf),
        "unites_hebergement": [_uh_node(uh) for uh in uf.unites_hebergement],
        "chambres": [],
        "lits": [],
    }


def _service_node(service: Service) -> dict[str, Any]:
    return {
        "id": service.id,
        "name": service.name,
        "type": "service",
        "status": _effective_status(service),
        "ufs": [_uf_node(uf) for uf in service.unites_fonctionnelles],
        "unites_hebergement": [],
        "chambres": [],
        "lits": [],
    }


def _pole_node(pole: Pole) -> dict[str, Any]:
    return {
        "id": pole.id,
        "name": pole.name,
        "type": "pole",
        "status": _effective_status(pole),
        "services": [_service_node(service) for service in pole.services],
        "ufs": [],
        "unites_hebergement": [],
        "chambres": [],
        "lits": [],
    }


def _eg_node(eg: EntiteGeographique) -> dict[str, Any]:
    return {
        "id": eg.id,
        "name": eg.name,
        "type": "eg",
        "status": _effective_status(eg),
        "poles": [_pole_node(pole) for pole in eg.poles],
        "services": [],
        "ufs": [],
        "unites_hebergement": [],
        "chambres": [],
        "lits": [],
    }


def build_structure_tree(
    session: Session,
    *,
    ej_context: int | None = None,
    eg_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Charge une hiérarchie bornée par le contexte puis la projette en JSON."""

    query = select(EntiteGeographique)
    if eg_ids:
        query = query.where(EntiteGeographique.id.in_(eg_ids))
    elif ej_context is not None:
        query = query.where(EntiteGeographique.entite_juridique_id == ej_context)

    query = query.options(
        selectinload(EntiteGeographique.poles)
        .selectinload(Pole.services)
        .selectinload(Service.unites_fonctionnelles)
        .selectinload(UniteFonctionnelle.unites_hebergement)
        .selectinload(UniteHebergement.chambres)
        .selectinload(Chambre.lits)
    )
    entities = session.exec(query).all()
    if (ej_context is not None or eg_ids) and not entities:
        return []

    poles = [pole for eg in entities for pole in eg.poles]
    services = [service for pole in poles for service in pole.services]
    ufs = [uf for service in services for uf in service.unites_fonctionnelles]
    uhs = [uh for uf in ufs for uh in uf.unites_hebergement]
    chambres = [chambre for uh in uhs for chambre in uh.chambres]
    lits = [lit for chambre in chambres for lit in chambre.lits]

    changed = False
    for level in (poles, services, ufs, uhs, chambres, lits):
        if apply_scheduled_status(level):
            changed = True
    if changed:
        session.commit()

    return [_eg_node(eg) for eg in entities]


__all__ = ["build_structure_tree", "build_structure_tree_for_template"]
