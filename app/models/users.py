"""Comptes locaux utilisés uniquement lorsque la sécurité est activée."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LocalUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(default="")
    password_hash: str
    roles_json: str = Field(default='["user"]')
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


__all__ = ["LocalUser"]
