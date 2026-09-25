"""Compatibilité historique des modèles de structure hospitalière.

Les modèles sont désormais regroupés dans :mod:`app.models.structure`.
"""

from app.models.structure import (
    BaseLocation,
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    GHTContext,
    IdentifierNamespace,
    Lit,
    LocationMode,
    LocationPhysicalType,
    LocationPositionType,
    LocationServiceType,
    LocationStatus,
    MedicalAuthorizationType,
    Pole,
    Service,
    StructureTemplate,
    StructureTemplateType,
    UFActivity,
    UniteActivite,
    UniteFonctionnelle,
    UniteFonctionnelleActivityLink,
    UniteHebergement,
)

__all__ = [
    "BaseLocation",
    "Chambre",
    "EntiteGeographique",
    "EntiteJuridique",
    "GHTContext",
    "IdentifierNamespace",
    "Lit",
    "LocationMode",
    "LocationPhysicalType",
    "LocationPositionType",
    "LocationServiceType",
    "LocationStatus",
    "MedicalAuthorizationType",
    "Pole",
    "Service",
    "StructureTemplate",
    "StructureTemplateType",
    "UFActivity",
    "UniteActivite",
    "UniteFonctionnelle",
    "UniteFonctionnelleActivityLink",
    "UniteHebergement",
]
