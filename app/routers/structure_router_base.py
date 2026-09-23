"""Routeurs et primitives partagés par les écrans de structure."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func
from sqlmodel import Session, select

from app.dependencies.ght import require_ght_context

LIT_OPERATIONAL_STATUS_OPTIONS = ["available", "occupied", "maintenance"]
DEFAULT_API_PAGE_SIZE = 100
MAX_API_PAGE_SIZE = 250


def execute_paginated(
    session: Session,
    response: Response,
    query: Any,
    *,
    order_by: tuple[Any, ...],
    skip: int,
    limit: int,
):
    """Exécute une liste paginée en exposant son total sans changer le JSON."""
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    response.headers["X-Total-Count"] = str(total)
    return session.exec(query.order_by(*order_by).offset(skip).limit(limit)).all()


def get_templates_with_filters(request: Request):
    """Retourne l'instance de templates configurée sur l'application."""
    return request.app.state.templates


router = APIRouter(prefix="/structure", tags=["structure"])
api_router = APIRouter(
    prefix="/api/structure",
    tags=["structure_api"],
    dependencies=[Depends(require_ght_context)],
)
redirect_router = APIRouter(prefix="/structure", tags=["structure_redirects"])


__all__ = [
    "DEFAULT_API_PAGE_SIZE",
    "LIT_OPERATIONAL_STATUS_OPTIONS",
    "MAX_API_PAGE_SIZE",
    "api_router",
    "execute_paginated",
    "get_templates_with_filters",
    "redirect_router",
    "router",
]
