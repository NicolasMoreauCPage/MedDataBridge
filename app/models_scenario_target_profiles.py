"""Compatibilité : profils de cible déplacés vers ``app.models``."""

from app.models.scenario_target_profiles import ScenarioTargetLocation, ScenarioTargetProfile

__all__ = ["ScenarioTargetLocation", "ScenarioTargetProfile"]
