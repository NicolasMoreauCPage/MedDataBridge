"""merge_hprim_fields

Revision ID: 9f1ac4d5253f
Revises: 754c8fad5f84, add_hprim_20251226
Create Date: 2025-12-26 12:22:15.670555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f1ac4d5253f'
down_revision: Union[str, Sequence[str], None] = ('754c8fad5f84', 'add_hprim_20251226')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
