import json

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.templating import Jinja2Templates
from pathlib import Path
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
async def hprim_messages_history(
    request: Request,
    session: Session = Depends(get_session),
    status: str | None = Query(None),
    direction: str | None = Query(None),
    patient_id: str | None = Query(None),
):
    query = select(HprimMessage)
    if status:
        query = query.where(HprimMessage.status == status)
    if direction:
        query = query.where(HprimMessage.direction == direction)
    if patient_id:
        query = query.where(HprimMessage.patient_id == patient_id)

    messages = list(session.exec(query.order_by(HprimMessage.created_at.desc())).all())
    stats = {
        "total": len(messages),
        "outbound": len([item for item in messages if item.direction == "outbound"]),
        "inbound": len([item for item in messages if item.direction == "inbound"]),
        "roundtrip": len([item for item in messages if item.direction == "roundtrip"]),
    }
    return templates.TemplateResponse(request, "hprim/persistent_messages.html", {
        "request": request,
        "title": "Historique HPRIM",
        "messages": messages,
        "stats": stats,
        "current_status": status,
        "current_direction": direction,
        "current_patient_id": patient_id,
    })


@router.get("/messages/{message_id}", summary="Détail d'un message HPRIM persistant")
async def hprim_message_detail(request: Request, message_id: str, session: Session = Depends(get_session)):
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