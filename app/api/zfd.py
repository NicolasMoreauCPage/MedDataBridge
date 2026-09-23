"""
API REST pour le segment ZFD (Complément démographique IHE France PAM)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select
from typing import List
from datetime import date
from app.db import get_session
from deployment.postgresql.app.models import ZFDSegment

router = APIRouter(prefix="/api/zfd", tags=["ZFD API"])


class ZFDSegmentCreate(BaseModel):
    patient_id: int | None = None
    mouvement_id: int | None = None
    zfd_1_date_lunaire: str | None = None
    zfd_2_semaines_gestation: int | None = None
    zfd_3_consentement_sms: str | None = None
    zfd_4_indicateur_naissance_modifiee: str | None = None
    zfd_5_mode_obtention_identite: str | None = None
    zfd_6_date_interrogation_insi: date | None = None
    zfd_7_justificatif_identite: str | None = None
    zfd_8_date_fin_validite_justificatif: date | None = None


class ZFDSegmentRead(ZFDSegmentCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


@router.post("/", response_model=ZFDSegmentRead, status_code=201)
def create_zfd_segment(zfd: ZFDSegmentCreate, session: Session = Depends(get_session)):
    zfd = ZFDSegment(**zfd.model_dump())
    session.add(zfd)
    session.commit()
    session.refresh(zfd)
    return zfd


@router.get("/{zfd_id}", response_model=ZFDSegmentRead)
def get_zfd_segment(zfd_id: int, session: Session = Depends(get_session)):
    zfd = session.get(ZFDSegment, zfd_id)
    if not zfd:
        raise HTTPException(status_code=404, detail="ZFD segment not found")
    return zfd


@router.get("/", response_model=List[ZFDSegmentRead])
def list_zfd_segments(session: Session = Depends(get_session)):
    return session.exec(select(ZFDSegment)).all()
