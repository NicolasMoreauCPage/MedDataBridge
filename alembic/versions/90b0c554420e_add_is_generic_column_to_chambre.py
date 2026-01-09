"""add_is_generic_column_to_chambre

Revision ID: 90b0c554420e
Revises: bdebea0e6af4
Create Date: 2025-12-20 13:42:24.032052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90b0c554420e'
down_revision: Union[str, Sequence[str], None] = 'bdebea0e6af4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_generic and max_occupancy columns to chambre table only if they don't exist
    try:
        op.add_column('chambre', sa.Column('is_generic', sa.Boolean(), nullable=True, default=False))
    except Exception:
        # Column may already exist
        pass
    try:
        op.add_column('chambre', sa.Column('max_occupancy', sa.Integer(), nullable=True, default=1))
    except Exception:
        # Column may already exist
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_generic and max_occupancy columns from chambre table
    try:
        op.drop_column('chambre', 'is_generic')
    except Exception:
        pass
    try:
        op.drop_column('chambre', 'max_occupancy')
    except Exception:
        pass
    op.drop_column('chambre', 'max_occupancy')
    op.drop_column('chambre', 'is_generic')
