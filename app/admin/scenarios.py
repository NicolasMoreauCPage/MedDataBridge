"""Vues admin pour les scénarios d'interopérabilité"""
from sqladmin import ModelView
from app.models_scenarios import InteropScenario, InteropScenarioStep


class InteropScenarioAdmin(ModelView, model=InteropScenario):
    name = "Interop Scenario"
    name_plural = "Interop Scenarios"
    icon = "fa-solid fa-project-diagram"


class InteropScenarioStepAdmin(ModelView, model=InteropScenarioStep):
    name = "Scenario Step"
    name_plural = "Scenario Steps"
    icon = "fa-solid fa-steps"
