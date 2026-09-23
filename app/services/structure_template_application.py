"""Application transactionnelle d'un modèle de structure hospitalière."""

from collections.abc import Sequence
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


class StructureTemplateValidationError(ValueError):
    """Le modèle ne peut pas produire une hiérarchie cohérente."""


class StructureTemplateTargetNotFoundError(LookupError):
    """L'entité géographique ciblée n'existe pas."""


def _validate_template(payload: dict[str, Any], hosting_units: Sequence[Any]) -> list[dict[str, Any]]:
    poles = payload.get("poles", [])
    if not isinstance(poles, list) or not poles:
        raise StructureTemplateValidationError(
            "La structure à générer doit contenir au moins un pôle."
        )

    uf_references: set[str] = set()
    for pole_index, pole in enumerate(poles, start=1):
        pole_name = pole.get("name") if isinstance(pole, dict) else None
        if not isinstance(pole_name, str) or not pole_name.strip():
            raise StructureTemplateValidationError(
                f"Le pôle {pole_index} doit avoir un nom."
            )
        services = pole.get("services", [])
        if not isinstance(services, list):
            raise StructureTemplateValidationError(
                f"Les services du pôle {pole_index} sont invalides."
            )
        for service_index, service in enumerate(services, start=1):
            service_name = service.get("name") if isinstance(service, dict) else None
            if not isinstance(service_name, str) or not service_name.strip():
                raise StructureTemplateValidationError(
                    f"Le service {service_index} du pôle {pole_index} doit avoir un nom."
                )
            ufs = service.get("ufs", [])
            if not isinstance(ufs, list):
                raise StructureTemplateValidationError(
                    f"Les UF du service {service_index} du pôle {pole_index} sont invalides."
                )
            for uf_index, uf in enumerate(ufs, start=1):
                uf_name = uf.get("name") if isinstance(uf, dict) else None
                if not isinstance(uf_name, str) or not uf_name.strip():
                    raise StructureTemplateValidationError(
                        f"L'UF {uf_index} du service {service_index} "
                        f"du pôle {pole_index} doit avoir un nom."
                    )
                uf_references.add(f"{pole_index - 1}:{service_index - 1}:{uf_index - 1}")

    for uh_index, hosting_unit in enumerate(hosting_units, start=1):
        name = hosting_unit.name.strip()
        if not name:
            raise StructureTemplateValidationError(
                f"L'unité d'hébergement {uh_index} doit avoir un nom."
            )
        if hosting_unit.uf_ref not in uf_references:
            raise StructureTemplateValidationError(
                f"L'UF de rattachement de l'unité d'hébergement {name} est introuvable"
            )
        if hosting_unit.chambres < 0 or hosting_unit.lits < 0:
            raise StructureTemplateValidationError(
                "Le nombre de chambres et de lits ne peut pas être négatif"
            )
        if hosting_unit.lits and not hosting_unit.chambres:
            raise StructureTemplateValidationError(
                f"L'unité d'hébergement {name} contient des lits sans chambre"
            )

    return poles


def apply_structure_template(
    session: Session,
    *,
    eg_id: int,
    payload: dict[str, Any],
    hosting_units: Sequence[Any],
) -> tuple[str, dict[str, int]]:
    """Valide puis crée toute la hiérarchie dans une transaction unique."""

    target = session.get(EntiteGeographique, eg_id)
    if target is None:
        raise StructureTemplateTargetNotFoundError(
            f"EntiteGeographique {eg_id} introuvable"
        )
    poles = _validate_template(payload, hosting_units)
    created = {
        "poles": 0,
        "services": 0,
        "ufs": 0,
        "uhs": 0,
        "chambres": 0,
        "lits": 0,
    }

    try:
        created_ufs: dict[str, int] = {}
        for pole_index, pole_data in enumerate(poles):
            pole = Pole(
                name=pole_data.get("name"),
                short_name=pole_data.get("short_name"),
                entite_geo_id=target.id,
                status=LocationStatus.ACTIVE,
            )
            session.add(pole)
            session.flush()
            created["poles"] += 1

            for service_index, service_data in enumerate(pole_data.get("services", [])):
                service = Service(
                    name=service_data.get("name"),
                    short_name=service_data.get("short_name"),
                    pole_id=pole.id,
                    status=LocationStatus.ACTIVE,
                )
                session.add(service)
                session.flush()
                created["services"] += 1

                for uf_index, uf_data in enumerate(service_data.get("ufs", [])):
                    uf = UniteFonctionnelle(
                        name=uf_data.get("name"),
                        um_code=uf_data.get("code_um"),
                        service_id=service.id,
                        status=LocationStatus.ACTIVE,
                    )
                    session.add(uf)
                    session.flush()
                    created_ufs[f"{pole_index}:{service_index}:{uf_index}"] = uf.id
                    created["ufs"] += 1

        for hosting_unit in hosting_units:
            uh = UniteHebergement(
                name=hosting_unit.name,
                unite_fonctionnelle_id=created_ufs[hosting_unit.uf_ref],
                status=LocationStatus.ACTIVE,
            )
            session.add(uh)
            session.flush()
            created["uhs"] += 1

            chambres = []
            for room_number in range(1, hosting_unit.chambres + 1):
                chambre = Chambre(
                    name=f"{hosting_unit.name} - Chambre {room_number}",
                    unite_hebergement_id=uh.id,
                    status=LocationStatus.ACTIVE,
                )
                session.add(chambre)
                session.flush()
                chambres.append(chambre)
                created["chambres"] += 1
            for bed_number in range(1, hosting_unit.lits + 1):
                chambre = chambres[(bed_number - 1) % len(chambres)]
                session.add(
                    Lit(
                        name=f"{hosting_unit.name} - Lit {bed_number}",
                        chambre_id=chambre.id,
                        status=LocationStatus.ACTIVE,
                    )
                )
                created["lits"] += 1

        session.commit()
    except Exception:
        session.rollback()
        raise

    return target.name, created


__all__ = [
    "StructureTemplateTargetNotFoundError",
    "StructureTemplateValidationError",
    "apply_structure_template",
]
