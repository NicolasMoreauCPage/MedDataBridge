"""File d'émission persistante, indépendante du transport."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class OutboundMessage(SQLModel, table=True):
    """Message à transmettre ou à rejouer après une indisponibilité partenaire."""

    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint_id: int = Field(foreign_key="systemendpoint.id", index=True)
    source_message_log_id: Optional[int] = Field(default=None, foreign_key="messagelog.id", index=True)
    protocol: str = Field(index=True)  # MLLP | FHIR
    message_type: Optional[str] = None
    correlation_id: Optional[str] = Field(default=None, index=True)
    payload: str
    status: str = Field(default="pending", index=True)  # pending|retry|sent|failed
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=8)
    next_attempt_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
