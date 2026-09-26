"""Clonage transactionnel d'un GHT pour préparer un environnement connecté.

Un GHT cloné conserve le référentiel métier (EJ et structure) mais reçoit une
nouvelle cible logicielle. Les destinations FHIR sont donc toutes dirigées vers
la nouvelle URL, sans conserver par erreur l'environnement d'origine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from sqlmodel import SQLModel, Session, select

from app.models.endpoints import FHIRConfig, FTPConfig, MLLPConfig
from app.models.scenario_config import ScenarioEJConfig
from app.models.shared import SystemEndpoint
from app.models.structure import (
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    GHTContext,
    IdentifierNamespace,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)


@dataclass(frozen=True)
class GHTCloneResult:
    context: GHTContext
    entity_count: int
    endpoint_count: int


def normalize_connected_software_url(value: str) -> tuple[str, str]:
    """Validate the FHIR base URL and return its canonical URL and hostname."""
    url = (value or "").strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError("L'URL du logiciel connecté doit être une URL HTTP(S) absolue.")
    if parsed.query or parsed.fragment:
        raise ValueError("L'URL du logiciel connecté ne doit contenir ni requête ni fragment.")
    return url, parsed.hostname


def _fields(source: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    """Copy scalar SQLModel fields while excluding PKs, audit fields and relations."""
    excluded = {
        "id", "identifier", "global_identifier", "created_at", "updated_at",
    } | (exclude or set())
    data: dict[str, Any] = {}
    for name, value in source.__dict__.items():
        if name.startswith("_") or name in excluded:
            continue
        if isinstance(value, (list, SQLModel)) or (value is not None and hasattr(value, "__table__")):
            continue
        data[name] = value
    return data


_NAMESPACE_PARENTS = {
    "ght_context_id", "entite_juridique_id", "entite_geographique_id", "pole_id",
    "service_id", "unite_fonctionnelle_id", "unite_hebergement_id", "chambre_id", "lit_id",
}


def _clone_namespaces(
    session: Session,
    source_id: int,
    *,
    source_column,
    target_column: str,
    target_id: int,
) -> None:
    for namespace in session.exec(select(IdentifierNamespace).where(source_column == source_id)).all():
        data = _fields(namespace, exclude=_NAMESPACE_PARENTS)
        data[target_column] = target_id
        session.add(IdentifierNamespace(**data))


def _clone_structure_for_ej(
    session: Session,
    source_ej: EntiteJuridique,
    target_context_id: int,
    timestamp: int,
) -> EntiteJuridique:
    """Clone one EJ, its hierarchy, namespaces and scenario configuration."""
    # ``entite_juridique_id`` is a legacy self-reference.  Keeping the source
    # value here would make the clone point back into the source environment.
    ej_data = _fields(source_ej, exclude={"ght_context_id", "entite_juridique_id"})
    ej_data.update(
        identifier=f"ej-clone-{timestamp}-{source_ej.id}",
        ght_context_id=target_context_id,
    )
    target_ej = EntiteJuridique(**ej_data)
    session.add(target_ej)
    session.flush()
    _clone_namespaces(
        session, source_ej.id, source_column=IdentifierNamespace.entite_juridique_id,
        target_column="entite_juridique_id", target_id=target_ej.id,
    )

    eg_map: dict[int, int] = {}
    pole_map: dict[int, int] = {}
    service_map: dict[int, int] = {}
    uf_map: dict[int, int] = {}
    uh_map: dict[int, int] = {}
    room_map: dict[int, int] = {}

    source_egs = session.exec(
        select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == source_ej.id)
    ).all()
    for entity in source_egs:
        data = _fields(entity, exclude={"entite_juridique_id"})
        data.update(identifier=f"eg-clone-{timestamp}-{entity.id}", entite_juridique_id=target_ej.id)
        target = EntiteGeographique(**data)
        session.add(target)
        session.flush()
        eg_map[entity.id] = target.id
        _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.entite_geographique_id,
                          target_column="entite_geographique_id", target_id=target.id)

    for source_id, target_id in eg_map.items():
        for entity in session.exec(select(Pole).where(Pole.entite_geo_id == source_id)).all():
            data = _fields(entity, exclude={"entite_geo_id", "entite_juridique_id"})
            data.update(identifier=f"pole-clone-{timestamp}-{entity.id}", entite_geo_id=target_id,
                        entite_juridique_id=target_ej.id)
            target = Pole(**data)
            session.add(target)
            session.flush()
            pole_map[entity.id] = target.id
            _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.pole_id,
                              target_column="pole_id", target_id=target.id)

    for source_id, target_id in pole_map.items():
        for entity in session.exec(select(Service).where(Service.pole_id == source_id)).all():
            data = _fields(entity, exclude={"pole_id"})
            data.update(identifier=f"service-clone-{timestamp}-{entity.id}", pole_id=target_id)
            target = Service(**data)
            session.add(target)
            session.flush()
            service_map[entity.id] = target.id
            _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.service_id,
                              target_column="service_id", target_id=target.id)

    for source_id, target_id in service_map.items():
        for entity in session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == source_id)).all():
            data = _fields(entity, exclude={"service_id"})
            data.update(identifier=f"uf-clone-{timestamp}-{entity.id}", service_id=target_id)
            target = UniteFonctionnelle(**data)
            session.add(target)
            session.flush()
            uf_map[entity.id] = target.id
            _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.unite_fonctionnelle_id,
                              target_column="unite_fonctionnelle_id", target_id=target.id)

    for source_id, target_id in uf_map.items():
        for entity in session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == source_id)).all():
            data = _fields(entity, exclude={"unite_fonctionnelle_id"})
            data.update(identifier=f"uh-clone-{timestamp}-{entity.id}", unite_fonctionnelle_id=target_id)
            target = UniteHebergement(**data)
            session.add(target)
            session.flush()
            uh_map[entity.id] = target.id
            _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.unite_hebergement_id,
                              target_column="unite_hebergement_id", target_id=target.id)

    for source_id, target_id in uh_map.items():
        for entity in session.exec(select(Chambre).where(Chambre.unite_hebergement_id == source_id)).all():
            data = _fields(entity, exclude={"unite_hebergement_id"})
            data.update(identifier=f"chambre-clone-{timestamp}-{entity.id}", unite_hebergement_id=target_id)
            target = Chambre(**data)
            session.add(target)
            session.flush()
            room_map[entity.id] = target.id
            _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.chambre_id,
                              target_column="chambre_id", target_id=target.id)

    for source_id, target_id in room_map.items():
        for entity in session.exec(select(Lit).where(Lit.chambre_id == source_id)).all():
            data = _fields(entity, exclude={"chambre_id"})
            data.update(identifier=f"lit-clone-{timestamp}-{entity.id}", chambre_id=target_id)
            target = Lit(**data)
            session.add(target)
            session.flush()
            _clone_namespaces(session, entity.id, source_column=IdentifierNamespace.lit_id,
                              target_column="lit_id", target_id=target.id)

    config = session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == source_ej.id)
    ).first()
    if config:
        data = _fields(config, exclude={"entite_juridique_id"})
        data["entite_juridique_id"] = target_ej.id
        for field_name in (
            "uf_hospitalisation_id", "uf_consultation_id", "uf_urgences_id", "uf_mutation_cible_id",
        ):
            source_uf_id = getattr(config, field_name, None)
            data[field_name] = uf_map.get(source_uf_id) if source_uf_id else None
        session.add(ScenarioEJConfig(**data))

    return target_ej


def _clone_endpoints(
    session: Session,
    source_context_id: int,
    target_context_id: int,
    ej_map: dict[int, int],
    connected_url: str,
    connected_hostname: str,
) -> int:
    source_endpoints = session.exec(
        select(SystemEndpoint).where(SystemEndpoint.ght_context_id == source_context_id)
    ).all()
    endpoint_map: dict[int, SystemEndpoint] = {}
    for endpoint in source_endpoints:
        data = _fields(endpoint, exclude={"ght_context_id", "entite_juridique_id", "linked_endpoint_id"})
        data.update(
            name=f"{endpoint.name} (Clone)",
            ght_context_id=target_context_id,
            entite_juridique_id=ej_map.get(endpoint.entite_juridique_id),
            linked_endpoint_id=None,
        )
        # L'URL reçue est la base FHIR exacte de la nouvelle version.
        if (endpoint.kind or "").upper() == "FHIR":
            data["base_url"] = connected_url
        # Pour les transports au nom d'hôte, seul un endpoint émetteur est
        # redirigé : un receiver doit conserver 0.0.0.0 / son bind local.
        if (endpoint.kind or "").upper() in {"MLLP", "FTP", "SFTP"} and (endpoint.role or "").lower() in {"sender", "both"}:
            data["host"] = connected_hostname
            if (endpoint.kind or "").upper() in {"FTP", "SFTP"}:
                data["ftp_host"] = connected_hostname
        target = SystemEndpoint(**data)
        session.add(target)
        session.flush()
        endpoint_map[endpoint.id] = target

        for config in session.exec(select(FHIRConfig).where(FHIRConfig.endpoint_id == endpoint.id)).all():
            config_data = _fields(config, exclude={"endpoint_id"})
            config_data.update(endpoint_id=target.id, name=f"{config.name} (Clone)", base_url=connected_url)
            session.add(FHIRConfig(**config_data))
        for config in session.exec(select(MLLPConfig).where(MLLPConfig.endpoint_id == endpoint.id)).all():
            config_data = _fields(config, exclude={"endpoint_id"})
            if (endpoint.role or "").lower() in {"sender", "both"}:
                config_data["host"] = connected_hostname
            config_data.update(endpoint_id=target.id, name=f"{config.name} (Clone)")
            session.add(MLLPConfig(**config_data))
        for config in session.exec(select(FTPConfig).where(FTPConfig.endpoint_id == endpoint.id)).all():
            config_data = _fields(config, exclude={"endpoint_id"})
            if (endpoint.role or "").lower() in {"sender", "both"}:
                config_data["host"] = connected_hostname
            config_data.update(endpoint_id=target.id, name=f"{config.name} (Clone)")
            session.add(FTPConfig(**config_data))

    for source in source_endpoints:
        if source.linked_endpoint_id and source.linked_endpoint_id in endpoint_map:
            endpoint_map[source.id].linked_endpoint_id = endpoint_map[source.linked_endpoint_id].id
            session.add(endpoint_map[source.id])
    return len(endpoint_map)


def clone_ght_context(
    session: Session,
    source: GHTContext,
    *,
    new_name: str,
    new_code: str,
    connected_software_url: str,
) -> GHTCloneResult:
    """Clone a complete GHT and point its connected-software endpoints to an URL.

    The caller owns the transaction: an exception leaves it free to rollback
    the complete clone, including every descendant and endpoint configuration.
    """
    url, hostname = normalize_connected_software_url(connected_software_url)
    new_name = new_name.strip()
    new_code = new_code.strip()
    if not new_name or not new_code:
        raise ValueError("Le nom et le code du nouveau GHT sont obligatoires.")
    if session.exec(select(GHTContext).where(GHTContext.code == new_code)).first():
        raise ValueError(f"Le code GHT « {new_code} » est déjà utilisé.")

    timestamp = int(datetime.utcnow().timestamp() * 1000)
    context_data = _fields(source, exclude={"name", "code", "fhir_server_url"})
    context_data.update(name=new_name, code=new_code, fhir_server_url=url)
    target = GHTContext(**context_data)
    session.add(target)
    session.flush()
    _clone_namespaces(session, source.id, source_column=IdentifierNamespace.ght_context_id,
                      target_column="ght_context_id", target_id=target.id)

    ej_map: dict[int, int] = {}
    source_entities = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.ght_context_id == source.id)
    ).all()
    for entity in source_entities:
        cloned_entity = _clone_structure_for_ej(session, entity, target.id, timestamp)
        ej_map[entity.id] = cloned_entity.id

    endpoint_count = _clone_endpoints(
        session, source.id, target.id, ej_map, url, hostname,
    )
    session.flush()
    return GHTCloneResult(target, len(ej_map), endpoint_count)
