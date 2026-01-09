"""Merge migration heads

Revision ID: 55e4f78776d3
Revises: 9a0b401add9e, 9f1ac4d5253f
Create Date: 2026-01-08 05:59:08.544474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55e4f78776d3'
down_revision: Union[str, Sequence[str], None] = ('9a0b401add9e', '9f1ac4d5253f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
