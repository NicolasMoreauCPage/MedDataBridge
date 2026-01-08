"""empty message

Revision ID: 9edb2ac575ce
Revises: ed0571d621c8
Create Date: 2025-12-26 12:10:44.261530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9edb2ac575ce'
down_revision: Union[str, Sequence[str], None] = 'ed0571d621c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
