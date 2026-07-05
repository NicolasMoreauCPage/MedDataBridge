"""add UniteActivite (UAC) table for FRCore 2.2.0 conformance

Revision ID: b2e4f0a13c9e
Revises: a1f3e9c02b7d
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e4f0a13c9e'
down_revision: Union[str, Sequence[str], None] = 'a1f3e9c02b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'uniteactivite',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('identifier', sa.String(), nullable=True),
        sa.Column('global_identifier', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('short_name', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('opening_date', sa.DateTime(), nullable=True),
        sa.Column('activation_date', sa.DateTime(), nullable=True),
        sa.Column('closing_date', sa.DateTime(), nullable=True),
        sa.Column('deactivation_date', sa.DateTime(), nullable=True),
        sa.Column('unite_fonctionnelle_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('discipline_prestation_code', sa.String(), nullable=True),
        sa.Column('tarif_code', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['unite_fonctionnelle_id'], ['unitefonctionnelle.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_uniteactivite_identifier'), 'uniteactivite', ['identifier'], unique=True)
    op.create_index(op.f('ix_uniteactivite_global_identifier'), 'uniteactivite', ['global_identifier'], unique=False)

    with op.batch_alter_table('identifiernamespace') as batch_op:
        batch_op.add_column(sa.Column('unite_activite_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_identifiernamespace_unite_activite_id', 'uniteactivite', ['unite_activite_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('identifiernamespace') as batch_op:
        batch_op.drop_constraint('fk_identifiernamespace_unite_activite_id', type_='foreignkey')
        batch_op.drop_column('unite_activite_id')

    op.drop_index(op.f('ix_uniteactivite_global_identifier'), table_name='uniteactivite')
    op.drop_index(op.f('ix_uniteactivite_identifier'), table_name='uniteactivite')
    op.drop_table('uniteactivite')
