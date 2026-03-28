"""API de consultation des messages HPRIM persistés."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlmodel import select

from app.db import get_session
from app.models.hprim_models import HprimMessage

router = APIRouter(prefix="/api/hprim/messages", tags=["HPRIM Messages"])


@router.get("")
async def list_hprim_messages(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    direction: Optional[str] = None,
    patient_id: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_session),
):
    statement = select(HprimMessage)
    if status:
        statement = statement.where(HprimMessage.status == status)
    if direction:
        statement = statement.where(HprimMessage.direction == direction)
    if patient_id:
        statement = statement.where(HprimMessage.patient_id == patient_id)
    if source:
        statement = statement.where(HprimMessage.source == source)
    if search:
        like_value = f"%{search}%"
        statement = statement.where(
            (HprimMessage.message_id.like(like_value))
            | (HprimMessage.xml_content.like(like_value))
            | (HprimMessage.filename.like(like_value))
        )

    all_items = list(db.exec(statement.order_by(HprimMessage.created_at.desc())).all())
    items = all_items[offset:offset + limit]

    return {
        "items": [
            {
                "message_id": item.message_id,
                "type_message": item.type_message,
                "direction": item.direction,
                "status": item.status,
                "patient_id": item.patient_id,
                "filename": item.filename,
                "source": item.source,
                "xml_size": item.xml_size,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ],
        "total": len(all_items),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{message_id}")
async def get_hprim_message_detail(message_id: str, db: Session = Depends(get_session)):
    item = db.get(HprimMessage, message_id)
    if not item:
        raise HTTPException(status_code=404, detail="Message HPRIM introuvable")

    validation_errors = []
    if item.validation_errors:
        try:
            validation_errors = json.loads(item.validation_errors)
        except json.JSONDecodeError:
            validation_errors = [{"message": item.validation_errors}]

    return {
        "message_id": item.message_id,
        "type_message": item.type_message,
        "direction": item.direction,
        "status": item.status,
        "patient_id": item.patient_id,
        "emetteur_id": item.emetteur_id,
        "destinataire_id": item.destinataire_id,
        "filename": item.filename,
        "source": item.source,
        "xml_size": item.xml_size,
        "validation_errors": validation_errors,
        "xml_content": item.xml_content,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }