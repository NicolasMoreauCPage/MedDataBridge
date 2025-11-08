"""Vues admin pour la connectivité système"""
from sqladmin import ModelView
from app.models_endpoints import SystemEndpoint
from app.models_shared import MessageLog


class SystemEndpointAdmin(ModelView, model=SystemEndpoint):
    name = "System Endpoint"
    name_plural = "System Endpoints"
    icon = "fa-solid fa-plug"


class MessageLogAdmin(ModelView, model=MessageLog):
    name = "Message Log"
    name_plural = "Message Logs"
    icon = "fa-solid fa-envelope"
    can_create = False
    can_edit = False
    can_delete = False
