"""Vues admin pour les scénarios d'interopérabilité"""
from sqladmin import ModelView
from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate, ScenarioTemplateStep


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
    column_labels = {"scenario_id": "Scenario", "order_index": "Ordre"}


class ScenarioTemplateAdmin(ModelView, model=ScenarioTemplate):
    column_list = [ScenarioTemplate.key, ScenarioTemplate.name, ScenarioTemplate.category, ScenarioTemplate.protocols_supported, ScenarioTemplate.is_active]
    column_searchable_list = [ScenarioTemplate.key, ScenarioTemplate.name, ScenarioTemplate.category, ScenarioTemplate.tags]
    column_sortable_list = [ScenarioTemplate.key, ScenarioTemplate.category, ScenarioTemplate.is_active]
    column_labels = {
        ScenarioTemplate.key: "Clé",
        ScenarioTemplate.name: "Nom",
        ScenarioTemplate.category: "Catégorie",
        ScenarioTemplate.protocols_supported: "Protocoles",
        ScenarioTemplate.is_active: "Actif",
    }


class ScenarioTemplateStepAdmin(ModelView, model=ScenarioTemplateStep):
    column_list = [ScenarioTemplateStep.template_id, ScenarioTemplateStep.order_index, ScenarioTemplateStep.semantic_event_code, ScenarioTemplateStep.hl7_event_code, ScenarioTemplateStep.message_role]
    column_searchable_list = [ScenarioTemplateStep.semantic_event_code, ScenarioTemplateStep.hl7_event_code, ScenarioTemplateStep.message_role]
    column_sortable_list = [ScenarioTemplateStep.template_id, ScenarioTemplateStep.order_index]
    column_labels = {
        ScenarioTemplateStep.template_id: "Template",
        ScenarioTemplateStep.order_index: "Ordre",
        ScenarioTemplateStep.semantic_event_code: "Événement sémantique",
        ScenarioTemplateStep.hl7_event_code: "HL7 Event",
        ScenarioTemplateStep.message_role: "Rôle",
    }
