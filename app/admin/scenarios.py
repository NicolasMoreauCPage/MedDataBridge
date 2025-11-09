"""Vues admin pour les scénarios d'interopérabilité"""
from sqladmin import ModelView
from app.models_scenarios import InteropScenario, InteropScenarioStep


class InteropScenarioAdmin(ModelView, model=InteropScenario):
    name = "Interop Scenario"
    name_plural = "Interop Scenarios"
    icon = "fa-solid fa-project-diagram"
    column_list = ["id", "name", "description", "scenario_type", "is_active"]
    column_searchable_list = ["name", "description"]
    column_sortable_list = ["id", "name", "scenario_type"]
    column_default_sort = ("name", False)


class InteropScenarioStepAdmin(ModelView, model=InteropScenarioStep):
    name = "Scenario Step"
    name_plural = "Scenario Steps"
    icon = "fa-solid fa-steps"
    column_list = ["id", "scenario_id", "step_order", "action_type", "description"]
    column_searchable_list = ["action_type", "description"]
    column_sortable_list = ["id", "step_order"]
    column_default_sort = ("step_order", False)
    column_labels = {"scenario_id": "Scenario"}
