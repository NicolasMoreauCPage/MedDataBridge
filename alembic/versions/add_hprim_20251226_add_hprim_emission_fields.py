"""add_hprim_emission_fields

Revision ID: add_hprim_20251226
Revises: 9edb2ac575ce
Create Date: 2025-12-26 12:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_hprim_20251226'
down_revision: Union[str, Sequence[str], None] = '9edb2ac575ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add HPRIM emission fields to systemendpoint
    op.add_column('systemendpoint', sa.Column('emit_hprim_ccam', sa.Boolean(), nullable=False, default=False))
    op.add_column('systemendpoint', sa.Column('emit_hprim_ngap', sa.Boolean(), nullable=False, default=False))
    op.add_column('systemendpoint', sa.Column('emit_hprim_ucd', sa.Boolean(), nullable=False, default=False))
    op.add_column('systemendpoint', sa.Column('emit_hprim_lpp', sa.Boolean(), nullable=False, default=False))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove HPRIM emission fields
    op.drop_column('systemendpoint', 'emit_hprim_lpp')
    op.drop_column('systemendpoint', 'emit_hprim_ucd')
    op.drop_column('systemendpoint', 'emit_hprim_ngap')
    op.drop_column('systemendpoint', 'emit_hprim_ccam')