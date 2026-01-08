"""Merge heads

Revision ID: f57e7c06af2c
Revises: bd558aad6d90, struct_tpl_001
Create Date: 2026-01-08 08:58:01.655092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f57e7c06af2c'
down_revision: Union[str, Sequence[str], None] = ('bd558aad6d90', 'struct_tpl_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
