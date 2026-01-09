"""Add cotations tracking columns to Dossier

Revision ID: db86856c4965
Revises: 55e4f78776d3
Create Date: 2026-01-08 05:59:12.008871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db86856c4965'
down_revision: Union[str, Sequence[str], None] = '55e4f78776d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add cotations tracking columns to Dossier"""
    # Add new columns to dossier table
    op.add_column('dossier', sa.Column('has_cotations', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('dossier', sa.Column('cotations_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema - Remove cotations tracking columns from Dossier"""
    # Remove columns from dossier table
    op.drop_column('dossier', 'cotations_count')
    op.drop_column('dossier', 'has_cotations')
