import json
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlmodel import select

from app.db import get_session
from app.models.hprim_models import HprimMessage

router = APIRouter(prefix="/hprim", tags=["HPRIM Management"])

templates_dir = str(Path(__file__).parent.parent / "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/test-files", summary="Interface de gestion des fichiers HPRIM de test")
async def hprim_test_files_interface(request: Request):
    """
    Interface web pour explorer, analyser et importer les fichiers HPRIM de test.
    """
    return templates.TemplateResponse(request, "hprim_test_files.html", {
        "request": request,
        "title": "Gestion HPRIM - Fichiers de Test"
    })

@router.get("/import", summary="Interface d'import HPRIM")
async def hprim_import_interface(request: Request):
    """
    Interface pour uploader et traiter des messages HPRIM entrants.
    """
    return templates.TemplateResponse(request, "hprim_import.html", {
        "request": request,
        "title": "Import HPRIM"
    })


@router.get("/messages", summary="Historique des messages HPRIM persistés")
def hprim_messages_history(
    request: Request,
    session: Session = Depends(get_session),
    status: str | None = Query(None),
    direction: str | None = Query(None),
    patient_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    filters = []
    if status:
        filters.append(HprimMessage.status == status)
    if direction:
        filters.append(HprimMessage.direction == direction)
    if patient_id:
        filters.append(HprimMessage.patient_id == patient_id)

    total = session.exec(
        select(func.count()).select_from(HprimMessage).where(*filters)
    ).one()
    messages = list(
        session.exec(
            select(HprimMessage)
            .where(*filters)
            .order_by(HprimMessage.created_at.desc(), HprimMessage.message_id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    direction_counts = dict(
        session.exec(
            select(HprimMessage.direction, func.count())
            .where(*filters)
            .group_by(HprimMessage.direction)
        ).all()
    )
    stats = {
        "total": total,
        "outbound": direction_counts.get("outbound", 0),
        "inbound": direction_counts.get("inbound", 0),
        "roundtrip": direction_counts.get("roundtrip", 0),
    }

    def page_url(target_offset: int) -> str:
        parameters = {
            key: value
            for key, value in {
                "status": status,
                "direction": direction,
                "patient_id": patient_id,
                "offset": target_offset,
                "limit": limit,
            }.items()
            if value not in (None, "")
        }
        return f"{request.url.path}?{urlencode(parameters)}"

    pagination = {
        "offset": offset,
        "limit": limit,
        "first_item": offset + 1 if messages else 0,
        "last_item": offset + len(messages),
        "has_previous": offset > 0,
        "has_next": offset + len(messages) < total,
        "previous_url": page_url(max(offset - limit, 0)),
        "next_url": page_url(offset + limit),
    }
    return templates.TemplateResponse(request, "hprim/persistent_messages.html", {
        "request": request,
        "title": "Historique HPRIM",
        "messages": messages,
        "stats": stats,
        "current_status": status,
        "current_direction": direction,
        "current_patient_id": patient_id,
        "pagination": pagination,
    })


@router.get("/messages/{message_id}", summary="Détail d'un message HPRIM persistant")
def hprim_message_detail(request: Request, message_id: str, session: Session = Depends(get_session)):
    message = session.get(HprimMessage, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message HPRIM introuvable")

    validation_errors = []
    if message.validation_errors:
        try:
            validation_errors = json.loads(message.validation_errors)
        except json.JSONDecodeError:
            validation_errors = [{"message": message.validation_errors}]

    return templates.TemplateResponse(request, "hprim/persistent_message_detail.html", {
        "request": request,
        "title": f"Message HPRIM {message.message_id}",
        "message": message,
        "validation_errors": validation_errors,
    })
