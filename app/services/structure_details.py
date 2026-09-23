"""Lecture et projection des fiches de structure."""

from typing import Any

from sqlmodel import Session

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


class UnknownStructureTypeError(ValueError):
    """Le type demandé ne correspond à aucun niveau de structure."""


class StructureEntityNotFoundError(LookupError):
    """L'entité demandée n'existe pas."""


MODEL_BY_TYPE = {
    "eg": EntiteGeographique,
    "pole": Pole,
    "service": Service,
    "uf": UniteFonctionnelle,
    "uh": UniteHebergement,
    "chambre": Chambre,
    "lit": Lit,
}

COMMON_ADDRESS_FIELDS = (
    "address_line1",
    "address_line2",
    "address_line3",
    "address_city",
    "address_postalcode",
    "address_country",
)

FIELDS_BY_TYPE = {
    "eg": ("finess", "category_code", "category_name"),
    "pole": ("typology", "operational_status"),
    "service": (
        "service_type",
        "typology",
        "operational_status",
        "etage",
        "aile",
        "type_chambre",
        "gender_usage",
    ),
    "uf": (
        "uf_type",
        "um_code",
        "typology",
        "operational_status",
        "etage",
        "aile",
        "type_chambre",
        "gender_usage",
    ),
    "uh": (
        "typology",
        "uf_type",
        "operational_status",
        "etage",
        "aile",
        "type_chambre",
        "gender_usage",
    ),
    "chambre": (
        "typology",
        "uf_type",
        "operational_status",
        "is_generic",
        "max_occupancy",
        "etage",
        "aile",
        "type_chambre",
        "gender_usage",
    ),
    "lit": (
        "typology",
        "uf_type",
        "operational_status",
        "is_generic",
        "max_occupancy",
        "etage",
        "aile",
        "type_chambre",
        "gender_usage",
    ),
}


def get_structure_details(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
) -> dict[str, Any]:
    """Retourne le contrat de détail commun à tous les niveaux de structure."""

    model = MODEL_BY_TYPE.get(entity_type)
    if model is None:
        raise UnknownStructureTypeError("Type invalide")
    entity = session.get(model, entity_id)
    if entity is None:
        raise StructureEntityNotFoundError("Entité non trouvée")

    resolver = getattr(entity, "get_effective_status", None)
    status = resolver() if callable(resolver) else getattr(entity, "status", None)
    if isinstance(status, LocationStatus):
        status = status.value
    details = {
        "id": entity.id,
        "name": entity.name,
        "type": entity_type,
        "identifier": getattr(entity, "identifier", None),
        "description": getattr(entity, "description", None),
        "status": status or "active",
    }
    for field in COMMON_ADDRESS_FIELDS:
        if hasattr(entity, field):
            details[field] = getattr(entity, field)
    for field in FIELDS_BY_TYPE[entity_type]:
        details[field] = getattr(entity, field, None)
    return details


__all__ = [
    "StructureEntityNotFoundError",
    "UnknownStructureTypeError",
    "get_structure_details",
]
