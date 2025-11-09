"""Vues admin pour les scénarios d'interopérabilité"""
from sqladmin import ModelView
from app.models_scenarios import InteropScenario, InteropScenarioStep


class InteropScenarioAdmin(ModelView, model=InteropScenario):
    name = "Interop Scenario"
    name_plural = "Interop Scenarios"
    icon = "fa-solid fa-project-diagram"
    column_list = ["id", "key", "name", "category", "protocol", "is_active"]
    column_searchable_list = ["key", "name", "description", "category"]
    column_sortable_list = ["id", "key", "name", "category", "protocol", "is_active"]
    column_default_sort = ("key", False)


class InteropScenarioStepAdmin(ModelView, model=InteropScenarioStep):
    name = "Scenario Step"
    name_plural = "Scenario Steps"
    icon = "fa-solid fa-steps"
    column_list = ["id", "scenario_id", "order_index", "name", "message_format", "message_type"]
    column_searchable_list = ["name", "description", "message_type"]
    column_sortable_list = ["id", "scenario_id", "order_index", "message_format"]
    column_default_sort = ("order_index", False)
    column_labels = {"scenario_id": "Scenario", "order_index": "Order"}
