"""add_hprim_emission_fields

Revision ID: 754c8fad5f84
Revises: 9edb2ac575ce
Create Date: 2025-12-26 12:20:49.506715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '754c8fad5f84'
down_revision: Union[str, Sequence[str], None] = '9edb2ac575ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
