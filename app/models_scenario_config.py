"""Compatibilité historique de la configuration des scénarios par EJ.

Le modèle et ses aides sont désormais regroupés dans
:mod:`app.models.scenario_config`.
"""

from app.models.scenario_config import (
    OID_RPPS,
    ScenarioEJConfig,
    build_xcn_field,
    get_location_for_event,
    get_medecin_for_event,
    get_medecin_traitant,
    get_uf_code_for_event,
)

__all__ = [
    "OID_RPPS",
    "ScenarioEJConfig",
    "build_xcn_field",
    "get_location_for_event",
    "get_medecin_for_event",
    "get_medecin_traitant",
    "get_uf_code_for_event",
]
