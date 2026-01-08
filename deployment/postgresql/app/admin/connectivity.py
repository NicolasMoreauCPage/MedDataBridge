"""Vues admin pour la connectivité système"""
from sqladmin import ModelView
from app.models_endpoints import SystemEndpoint
from app.models_shared import MessageLog


class SystemEndpointAdmin(ModelView, model=SystemEndpoint):
    name = "System Endpoint"
    name_plural = "System Endpoints"
    icon = "fa-solid fa-plug"
    column_list = ["id", "name", "kind", "role", "host", "port", "is_active"]
    column_searchable_list = ["name", "host"]
    column_sortable_list = ["id", "name", "kind", "role"]
    column_default_sort = ("name", False)


class MessageLogAdmin(ModelView, model=MessageLog):
    name = "Message Log"
    name_plural = "Message Logs"
    icon = "fa-solid fa-envelope"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ["id", "direction", "endpoint_id", "message_type", "created_at", "status"]
    column_searchable_list = ["message_type", "status"]
    column_sortable_list = ["id", "created_at", "direction"]
    column_default_sort = ("created_at", True)
    column_labels = {"endpoint_id": "Endpoint"}
