"""Pilotage simple de l'outbox persistante."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models.outbox import OutboundMessage
from app.services.outbox_service import (
    enqueue_failed_message_logs,
    outbox_stats,
    process_due_messages,
    retry_now,
)

router = APIRouter(prefix="/outbox", tags=["outbox"])


@router.get("/stats")
def get_outbox_stats(session: Session = Depends(get_session)):
    return outbox_stats(session)


@router.get("")
def list_outbox(status: str | None = Query(None), session: Session = Depends(get_session)):
    statement = select(OutboundMessage).order_by(OutboundMessage.created_at.desc())
    if status:
        statement = statement.where(OutboundMessage.status == status)
    return session.exec(statement.limit(500)).all()


@router.post("/recover")
def recover_failed_emissions(session: Session = Depends(get_session)):
    created = enqueue_failed_message_logs(session)
    session.commit()
    return {"created": created}


@router.post("/process")
async def process_outbox(limit: int = Query(100, ge=1, le=500), session: Session = Depends(get_session)):
    return await process_due_messages(session, limit=limit)


@router.post("/{outbox_id}/retry")
def retry_outbox(outbox_id: int, session: Session = Depends(get_session)):
    try:
        row = retry_now(session, outbox_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return row
