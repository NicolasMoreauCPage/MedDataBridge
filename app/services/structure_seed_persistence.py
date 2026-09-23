"""Persistance idempotente des niveaux de la structure de démonstration."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import Session, select

from app.models_structure import (
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    GHTContext,
    Lit,
    LocationMode,
    LocationPhysicalType,
    LocationServiceType,
    LocationStatus,
    Pole,
    Service,
    UFActivity,
    UniteFonctionnelle,
    UniteHebergement,
)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value

def _ensure_entite_juridique(
    session: Session,
    context: GHTContext,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> EntiteJuridique:
    """Crée ou met à jour l'entité juridique (EJ) identifiée par finess_ej.
    
    L'EJ représente l'établissement au niveau juridique (FINESS EJ, SIREN, SIRET).
    Rattachée au GHTContext pour isolement multi-tenant.
    
    Args:
        session: Session DB
        context: GHTContext auquel rattacher l'EJ
        data: Dictionnaire de configuration (name, finess_ej, siren, siret, address...)
        stats: Compteurs created/updated
    
    Returns:
        Instance EntiteJuridique créée ou mise à jour
    """
    ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == data["finess_ej"])
    ).first()

    values = {
        "name": data["name"],
        "short_name": data.get("short_name"),
        "description": data.get("description"),
        "finess_ej": data["finess_ej"],
        "siren": data.get("siren"),
        "siret": data.get("siret"),
        "address_line": data.get("address_line"),
        "postal_code": data.get("postal_code"),
        "city": data.get("city"),
        "country": data.get("country", "FR"),
        "is_active": data.get("is_active", True),
    }

    if ej is None:
        ej = EntiteJuridique(ght_context_id=context.id, **values)
        session.add(ej)
        session.flush()
        stats["created"]["entite_juridique"] += 1
    else:
        for field, value in values.items():
            setattr(ej, field, value)
        ej.ght_context_id = context.id
        ej.updated_at = datetime.utcnow()
        stats["updated"]["entite_juridique"] += 1

    return ej


def _ensure_entite_geographique(
    session: Session,
    entite_juridique: EntiteJuridique,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> EntiteGeographique:
    """Crée ou met à jour une entité géographique (EG / site) identifiée par identifier.
    
    L'EG représente un site hospitalier avec FINESS géographique, adresse, coordonnées GPS.
    Rattachée à une EntiteJuridique parente.
    
    Args:
        session: Session DB
        entite_juridique: EJ parente
        data: Dictionnaire de configuration (identifier, name, finess, address, latitude/longitude...)
        stats: Compteurs created/updated
    
    Returns:
        Instance EntiteGeographique créée ou mise à jour
    """
    identifier = data["identifier"]
    eg = session.exec(
        select(EntiteGeographique).where(EntiteGeographique.identifier == identifier)
    ).first()

    values = {
        "name": data["name"],
        "short_name": data.get("short_name"),
        "description": data.get("description"),
        "status": _enum_value(data.get("status", LocationStatus.ACTIVE)),
        "mode": _enum_value(data.get("mode", LocationMode.INSTANCE)),
        "physical_type": _enum_value(data.get("physical_type", LocationPhysicalType.SI)),
        "finess": data["finess"],
        "address_line1": data.get("address_line1"),
        "address_line2": data.get("address_line2"),
        "address_line3": data.get("address_line3"),
        "address_postalcode": data.get("address_postalcode"),
        "address_city": data.get("address_city"),
        "address_country": data.get("address_country", "FR"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "type": data.get("type"),
        "category_code": data.get("category_code"),
        "category_name": data.get("category_name"),
        "category_sae": data.get("category_sae"),
    }

    if eg is None:
        eg = EntiteGeographique(
            identifier=identifier,
            entite_juridique_id=entite_juridique.id,
            **values,
        )
        session.add(eg)
        session.flush()
        stats["created"]["entite_geographique"] += 1
    else:
        for field, value in values.items():
            setattr(eg, field, value)
        eg.entite_juridique_id = entite_juridique.id
        eg.updated_at = datetime.utcnow()
        stats["updated"]["entite_geographique"] += 1

    return eg


def _ensure_pole(
    session: Session,
    entite_geo: EntiteGeographique,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Pole:
    """Crée ou met à jour un pôle identifié par identifier.
    
    Le Pôle regroupe plusieurs services sous une entité géographique.
    physicalType par défaut : 'area'.
    
    Args:
        session: Session DB
        entite_geo: EG parente
        data: Dictionnaire de configuration (identifier, name, short_name, description...)
        stats: Compteurs created/updated
    
    Returns:
        Instance Pole créée ou mise à jour
    """
    identifier = data["identifier"]
    pole = session.exec(select(Pole).where(Pole.identifier == identifier)).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.AREA,
    )

    if pole is None:
        pole = Pole(identifier=identifier, entite_geo_id=entite_geo.id, **values)
        session.add(pole)
        session.flush()
        stats["created"]["pole"] += 1
    else:
        for field, value in values.items():
            setattr(pole, field, value)
        pole.entite_geo_id = entite_geo.id
        stats["updated"]["pole"] += 1

    return pole


def _ensure_service(
    session: Session,
    pole: Pole,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Service:
    """Crée ou met à jour un service identifié par identifier.
    
    Le Service représente une unité de soins avec service_type (MCO, SSR, PSY...),
    typologie, et optionnellement un responsable (RPPS, ADELI, spécialité).
    physicalType par défaut : 'bu' (building).
    
    Args:
        session: Session DB
        pole: Pole parent
        data: Dictionnaire de configuration (identifier, name, service_type, typology, responsible_*)
        stats: Compteurs created/updated
    
    Returns:
        Instance Service créée ou mise à jour
    """
    identifier = data["identifier"]
    service = session.exec(select(Service).where(Service.identifier == identifier)).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.BU,
    )
    values.update(
        {
            "service_type": data.get("service_type", LocationServiceType.MCO),
            "typology": data.get("typology"),
            "responsible_id": data.get("responsible_id"),
            "responsible_name": data.get("responsible_name"),
            "responsible_firstname": data.get("responsible_firstname"),
            "responsible_rpps": data.get("responsible_rpps"),
            "responsible_adeli": data.get("responsible_adeli"),
            "responsible_specialty": data.get("responsible_specialty"),
        }
    )

    if service is None:
        service = Service(identifier=identifier, pole_id=pole.id, **values)
        session.add(service)
        session.flush()
        stats["created"]["service"] += 1
    else:
        for field, value in values.items():
            setattr(service, field, value)
        service.pole_id = pole.id
        stats["updated"]["service"] += 1

    return service


def _ensure_unite_fonctionnelle(
    session: Session,
    service: Service,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> UniteFonctionnelle:
    """Crée ou met à jour une unité fonctionnelle (UF) identifiée par identifier.
    
    L'UF représente une unité de production de soins avec um_code (code UM), 
    uf_type (hospitalisation, consultations, urgences...).
    Supporte les activités multiples via uf_activities (relation N-N avec UFActivity).
    physicalType par défaut : 'fl' (floor).
    
    Args:
        session: Session DB
        service: Service parent
        data: Dictionnaire de configuration (identifier, name, um_code, uf_type, uf_activities list)
        stats: Compteurs created/updated
    
    Returns:
        Instance UniteFonctionnelle créée ou mise à jour
    """
    identifier = data["identifier"]
    uf = session.exec(
        select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == identifier)
    ).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.FL,
    )
    values.update(
        {
            "um_code": data.get("um_code"),
            "uf_type": data.get("uf_type"),
        }
    )

    if uf is None:
        uf = UniteFonctionnelle(identifier=identifier, service_id=service.id, **values)
        session.add(uf)
        session.flush()
        stats["created"]["unite_fonctionnelle"] += 1
    else:
        for field, value in values.items():
            setattr(uf, field, value)
        uf.service_id = service.id
        stats["updated"]["unite_fonctionnelle"] += 1

    # Synchroniser les activités UF (multi-valué)
    _sync_uf_activities(session, uf, data, stats)

    return uf


def _ensure_unite_hebergement(
    session: Session,
    uf: UniteFonctionnelle,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> UniteHebergement:
    """Crée ou met à jour une unité d'hébergement (UH) identifiée par identifier.
    
    L'UH regroupe des chambres sur un étage/aile spécifique.
    physicalType par défaut : 'wi' (wing).
    
    Args:
        session: Session DB
        uf: UniteFonctionnelle parente
        data: Dictionnaire de configuration (identifier, name, etage, aile)
        stats: Compteurs created/updated
    
    Returns:
        Instance UniteHebergement créée ou mise à jour
    """
    identifier = data["identifier"]
    uh = session.exec(
        select(UniteHebergement).where(UniteHebergement.identifier == identifier)
    ).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.WI,
    )
    values.update(
        {
            "etage": data.get("etage"),
            "aile": data.get("aile"),
        }
    )

    if uh is None:
        uh = UniteHebergement(
            identifier=identifier,
            unite_fonctionnelle_id=uf.id,
            **values,
        )
        session.add(uh)
        session.flush()
        stats["created"]["unite_hebergement"] += 1
    else:
        for field, value in values.items():
            setattr(uh, field, value)
        uh.unite_fonctionnelle_id = uf.id
        stats["updated"]["unite_hebergement"] += 1

    return uh


def _ensure_chambre(
    session: Session,
    uh: UniteHebergement,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Chambre:
    """Crée ou met à jour une chambre identifiée par identifier.
    
    La chambre contient un ou plusieurs lits avec type_chambre (simple, double, box...).
    physicalType par défaut : 'ro' (room).
    
    Args:
        session: Session DB
        uh: UniteHebergement parente
        data: Dictionnaire de configuration (identifier, name, type_chambre, gender_usage)
        stats: Compteurs created/updated
    
    Returns:
        Instance Chambre créée ou mise à jour
    """
    identifier = data["identifier"]
    chambre = session.exec(
        select(Chambre).where(Chambre.identifier == identifier)
    ).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.RO,
    )
    values.update(
        {
            "type_chambre": data.get("type_chambre"),
            "gender_usage": data.get("gender_usage"),
        }
    )

    if chambre is None:
        chambre = Chambre(
            identifier=identifier,
            unite_hebergement_id=uh.id,
            **values,
        )
        session.add(chambre)
        session.flush()
        stats["created"]["chambre"] += 1
    else:
        for field, value in values.items():
            setattr(chambre, field, value)
        chambre.unite_hebergement_id = uh.id
        stats["updated"]["chambre"] += 1

    return chambre


def _ensure_lit(
    session: Session,
    chambre: Chambre,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Lit:
    """Crée ou met à jour un lit identifié par identifier.
    
    Le lit est l'unité atomique d'hébergement avec operational_status (available, occupied, maintenance...).
    physicalType par défaut : 'bd' (bed).
    
    Args:
        session: Session DB
        chambre: Chambre parente
        data: Dictionnaire de configuration (identifier, name, operational_status)
        stats: Compteurs created/updated
    
    Returns:
        Instance Lit créée ou mise à jour
    """
    identifier = data["identifier"]
    lit = session.exec(select(Lit).where(Lit.identifier == identifier)).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.BD,
    )
    values.update(
        {
            "operational_status": data.get("operational_status"),
        }
    )

    if lit is None:
        lit = Lit(identifier=identifier, chambre_id=chambre.id, **values)
        session.add(lit)
        session.flush()
        stats["created"]["lit"] += 1
    else:
        for field, value in values.items():
            setattr(lit, field, value)
        lit.chambre_id = chambre.id
        stats["updated"]["lit"] += 1

    return lit


def _base_location_values(
    data: Dict[str, Any],
    *,
    default_physical_type: LocationPhysicalType,
) -> Dict[str, Any]:
    """Extrait les champs communs BaseLocation depuis un dictionnaire de configuration.
    
    Applique les valeurs par défaut pour status (ACTIVE), mode (INSTANCE), physical_type (paramétré).
    Utilisé par toutes les fonctions _ensure_* pour normaliser les valeurs avant insertion/update.
    
    Args:
        data: Dictionnaire de configuration (name, short_name, description, status, mode, physical_type, address_*)
        default_physical_type: Valeur par défaut pour physical_type si absente
    
    Returns:
        Dictionnaire de valeurs pour BaseLocation (name, status, mode, physical_type, address_*)
    """
    return {
        "name": data["name"],
        "short_name": data.get("short_name"),
        "description": data.get("description"),
        "status": data.get("status", LocationStatus.ACTIVE),
        "mode": data.get("mode", LocationMode.INSTANCE),
        "physical_type": data.get("physical_type", default_physical_type),
        "address_line1": data.get("address_line1"),
        "address_line2": data.get("address_line2"),
        "address_line3": data.get("address_line3"),
        "address_city": data.get("address_city"),
        "address_postalcode": data.get("address_postalcode"),
        "address_country": data.get("address_country"),
        "opening_date": data.get("opening_date"),
        "activation_date": data.get("activation_date"),
        "closing_date": data.get("closing_date"),
        "deactivation_date": data.get("deactivation_date"),
    }


def _ensure_uf_activity(session: Session, code: str) -> UFActivity:
    """Crée ou récupère une UFActivity identifiée par code.
    
    Les UFActivity sont des codes métier (ex: 'urgences', 'consultations', 'hospitalisation')
    utilisés pour décrire les activités d'une unité fonctionnelle (relation N-N).
    
    Args:
        session: Session DB
        code: Code d'activité (normalisé en minuscules)
    
    Returns:
        Instance UFActivity créée ou existante
    
    Raises:
        ValueError: si code est vide
    """
    code = (code or "").strip().lower()
    if not code:
        raise ValueError("UF activity code must be non-empty")
    act = session.exec(select(UFActivity).where(UFActivity.code == code)).first()
    if act is None:
        act = UFActivity(code=code, display=code.title(), system="http://interop-sante.fr/fhir/CodeSystem/fr-uf-type")
        session.add(act)
        session.flush()
    return act


def _sync_uf_activities(session: Session, uf: UniteFonctionnelle, data: Dict[str, Any], stats: Dict[str, Counter]) -> None:
    """Synchronise la liste d'activités (relation N-N) d'une UniteFonctionnelle.
    
    Ajoute les activités manquantes, supprime les obsolètes.
    Source de codes : data["uf_activities"] (liste) ou data["uf_type"] (fallback unique).
    
    Args:
        session: Session DB
        uf: UniteFonctionnelle à synchroniser
        data: Dictionnaire de configuration (uf_activities ou uf_type)
        stats: Compteurs (non utilisé ici mais passé pour cohérence)
    """
    # Détermination des codes depuis la structure fournie
    codes: List[str] = []
    if isinstance(data.get("uf_activities"), list) and data["uf_activities"]:
        codes = [str(x) for x in data["uf_activities"] if x]
    elif data.get("uf_type"):
        codes = [str(data["uf_type"])]

    if not codes:
        return

    # Créer/obtenir les UFActivity puis synchroniser la relation
    activities = [_ensure_uf_activity(session, c) for c in codes]

    # Charger l'entité fraîche pour la relation (si nécessaire)
    session.refresh(uf)
    current_ids = {a.id for a in getattr(uf, "activities", []) if a and a.id}
    desired_ids = {a.id for a in activities if a and a.id}

    # Ajouter les manquantes
    to_add = [a for a in activities if a.id not in current_ids]
    if to_add:
        for a in to_add:
            uf.activities.append(a)
        stats["created"]["uf_activity_link"] += len(to_add)

    # Retirer les obsolètes (ne pas forcer si on ne veut que enrichir)
    to_remove = [a for a in getattr(uf, "activities", []) if a.id not in desired_ids]
    for a in to_remove:
        uf.activities.remove(a)
        stats["updated"]["uf_activity_link_removed"] += 1

    session.add(uf)
    session.flush()
