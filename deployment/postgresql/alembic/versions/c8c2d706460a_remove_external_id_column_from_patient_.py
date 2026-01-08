"""Remove external_id column from patient, dossier, venue, mouvement

Revision ID: c8c2d706460a
Revises: 5fc898b68be8
Create Date: 2025-12-06 11:37:27.713778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8c2d706460a'
down_revision: Union[str, Sequence[str], None] = '5fc898b68be8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Remove external_id column from patient table."""
    # Drop external_id column from patient table (only table that has it)
    with op.batch_alter_table('patient', schema=None) as batch_op:
        batch_op.drop_column('external_id')


def downgrade() -> None:
    """Downgrade schema - Re-add external_id column to patient table."""
    # Re-add external_id column to patient table
    with op.batch_alter_table('patient', schema=None) as batch_op:
        batch_op.add_column(sa.Column('external_id', sa.VARCHAR(), nullable=True))
