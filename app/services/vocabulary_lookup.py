"""Service utilitaire pour récupérer dynamiquement les options de vocabulaire.

Objectif : centraliser les listes de valeurs aujourd'hui dupliquées dans
`helpers.py` (status, mode, physical_type, service_type) et permettre leur
paramétrage via les tables VocabularySystem/VocabularyValue existantes et les
pages d'administration.

Si un système de vocabulaire n'existe pas encore en base, on retourne en
fallback les valeurs Enum codées (pour compatibilité immédiate). Cela permet
une migration progressive : on peut créer les systèmes correspondants ensuite
via l'initialisation ou l'UI sans casser les écrans.
"""
from typing import List, Dict
from sqlmodel import select

from app.db import session_factory
from app.models_vocabulary import VocabularySystem, VocabularyValue
from app.models_structure import (
    LocationStatus,
    LocationMode,
    LocationPhysicalType,
    LocationServiceType,
)

# Mapping interne entre noms "logiques" et noms techniques des systèmes.
# Ces noms techniques pourront être modifiés dans l'UI si besoin sans changer
# le code applicatif (grâce au champ name de VocabularySystem).
SYSTEM_NAME_MAP = {
    "location-status": "location-status",
    "location-mode": "location-mode",
    "location-physical-type": "location-physical-type",
    "location-service-type": "location-service-type",
}


def _system_values(system_name: str) -> List[Dict[str, str]]:
    """Récupère les valeurs actives d'un système de vocabulaire.

    Retourne une liste de dict {value, label}. Si le système n'existe pas
    (migration progressive), retourne une liste vide.
    """
    with session_factory() as session:
        system = session.exec(
            select(VocabularySystem).where(VocabularySystem.name == system_name)
        ).first()
        if not system:
            return []
        # Charger valeurs actives triées par order
        values = session.exec(
            select(VocabularyValue)
            .where(VocabularyValue.system_id == system.id)
            .where(VocabularyValue.is_active == True)  # noqa: E712
            .order_by(VocabularyValue.order)
        ).all()
        return [
            {"value": v.code, "label": v.display or v.code}
            for v in values
        ]


def get_vocabulary_options(logical_name: str) -> List[Dict[str, str]]:
    """Point d'entrée unique pour récupérer les options.

    - Cherche d'abord dans VocabularySystem/VocabularyValue
    - Sinon fallback sur les Enum internes
    """
    system_name = SYSTEM_NAME_MAP.get(logical_name, logical_name)
    values = _system_values(system_name)
    if values:
        return values

    # Fallbacks : conversion des Enum internes vers structure homogène
    if logical_name == "location-status":
        return [{"value": e.value, "label": e.value} for e in LocationStatus]
    if logical_name == "location-mode":
        return [{"value": e.value, "label": e.value} for e in LocationMode]
    if logical_name == "location-physical-type":
        return [{"value": e.value, "label": e.value} for e in LocationPhysicalType]
    if logical_name == "location-service-type":
        return [{"value": e.value, "label": e.value} for e in LocationServiceType]

    return []


def ensure_system_exists(logical_name: str, enum_values: List[Dict[str, str]]) -> None:
    """Création opportuniste d'un système si absent (mode automatique).

    Utilisable dans une tâche d'initialisation : permet de transformer les
    valeurs enum existantes en vocabulaire paramétrable sans écrire une
    migration lourde. Non appelé automatiquement pour éviter les écritures
    implicites à chaque requête.
    """
    system_name = SYSTEM_NAME_MAP.get(logical_name, logical_name)
    with session_factory() as session:
        existing = session.exec(
            select(VocabularySystem).where(VocabularySystem.name == system_name)
        ).first()
        if existing:
            return
        system = VocabularySystem(
            name=system_name,
            label=f"{logical_name} (auto-import)",
            system_type="LOCAL",  # type local paramétrable
            is_user_defined=True,
        )
        system.values = [
            VocabularyValue(
                code=v["value"],
                display=v.get("label", v["value"]),
                order=i + 1,
            )
            for i, v in enumerate(enum_values)
        ]
        session.add(system)
        session.commit()
