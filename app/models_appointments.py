"""Persistance minimale des rendez-vous HL7 v2 SIU."""

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Appointment(SQLModel, table=True):
    """Projection locale d'un rendez-vous ``SIU^Sxx``.

    Le modèle conserve les identifiants fonctionnels du segment SCH plutôt que
    de transformer un rendez-vous en venue PAM : les deux domaines sont liés,
    mais distincts en HL7 v2.
    """

    __table_args__ = (
        UniqueConstraint("external_id", "assigning_authority", name="uq_appointment_external_authority"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True)
    assigning_authority: str = Field(default="", index=True)
    patient_identifier: Optional[str] = Field(default=None, index=True)
    patient_id: Optional[int] = Field(default=None, foreign_key="patient.id", index=True)
    status: str = Field(default="booked", index=True)
    start_at: Optional[datetime] = Field(default=None, index=True)
    end_at: Optional[datetime] = Field(default=None, index=True)
    service_code: Optional[str] = None
    location_code: Optional[str] = None
    practitioner_identifier: Optional[str] = None
    last_trigger: str = Field(default="S12", index=True)
    source_endpoint_id: Optional[int] = Field(default=None, foreign_key="systemendpoint.id", index=True)
    source_payload: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
