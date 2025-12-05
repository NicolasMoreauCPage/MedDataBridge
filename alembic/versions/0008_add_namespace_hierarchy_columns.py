"""Add structural hierarchy columns to IdentifierNamespace

Revision ID: 0008_add_namespace_hierarchy_columns
Revises: 0007_add_location_fields_ej_config
Create Date: 2025-12-05 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_add_namespace_hierarchy_columns'
down_revision: Union[str, Sequence[str], None] = '0007_add_location_fields_ej_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add structural hierarchy columns to identifiernamespace."""
    # Add columns for structural hierarchy
    with op.batch_alter_table('identifiernamespace') as batch_op:
        batch_op.add_column(sa.Column('entite_geographique_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('pole_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('service_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('unite_fonctionnelle_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('unite_hebergement_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('chambre_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('lit_id', sa.INTEGER(), nullable=True))


def downgrade() -> None:
    """Remove structural hierarchy columns."""
    with op.batch_alter_table('identifiernamespace') as batch_op:
        batch_op.drop_column('lit_id')
        batch_op.drop_column('chambre_id')
        batch_op.drop_column('unite_hebergement_id')
        batch_op.drop_column('unite_fonctionnelle_id')
        batch_op.drop_column('service_id')
        batch_op.drop_column('pole_id')
        batch_op.drop_column('entite_geographique_id')
