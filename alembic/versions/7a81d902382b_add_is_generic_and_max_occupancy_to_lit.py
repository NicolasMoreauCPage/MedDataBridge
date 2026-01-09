"""add_is_generic_and_max_occupancy_to_lit

Revision ID: 7a81d902382b
Revises: 90b0c554420e
Create Date: 2025-12-20 13:43:49.624675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a81d902382b'
down_revision: Union[str, Sequence[str], None] = '90b0c554420e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_generic column to lit table only if it doesn't exist
    try:
        op.add_column('lit', sa.Column('is_generic', sa.Boolean(), nullable=True, default=False))
    except Exception:
        pass
    # Add max_occupancy column to lit table only if it doesn't exist
    try:
        op.add_column('lit', sa.Column('max_occupancy', sa.Integer(), nullable=True, default=1))
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    try:
        op.drop_column('lit', 'is_generic')
    except Exception:
        pass
    try:
        op.drop_column('lit', 'max_occupancy')
    except Exception:
        pass
    # Remove max_occupancy column from lit table
    op.drop_column('lit', 'max_occupancy')
    # Remove is_generic column from lit table
    op.drop_column('lit', 'is_generic')
