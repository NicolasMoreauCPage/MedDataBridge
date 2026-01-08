# Minimal shim for hprim_models to avoid import errors in tests
# This module provides placeholder classes for HPRIM-related models

from sqlmodel import SQLModel, Field
from typing import Optional

class HprimMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str

# Add other classes as needed to satisfy imports