"""
API REST pour le segment ZFD (Complément démographique IHE France PAM)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.db import get_session
from deployment.postgresql.app.models import ZFDSegment

router = APIRouter(prefix="/api/zfd", tags=["ZFD API"])

@router.post("/", response_model=ZFDSegment, status_code=201)
async def create_zfd_segment(zfd: ZFDSegment, session: Session = Depends(get_session)):
    session.add(zfd)
    session.commit()
    session.refresh(zfd)
    return zfd

@router.get("/{zfd_id}", response_model=ZFDSegment)
async def get_zfd_segment(zfd_id: int, session: Session = Depends(get_session)):
    zfd = session.get(ZFDSegment, zfd_id)
    if not zfd:
        raise HTTPException(status_code=404, detail="ZFD segment not found")
    return zfd

@router.get("/", response_model=List[ZFDSegment])
async def list_zfd_segments(session: Session = Depends(get_session)):
    return session.exec(select(ZFDSegment)).all()
