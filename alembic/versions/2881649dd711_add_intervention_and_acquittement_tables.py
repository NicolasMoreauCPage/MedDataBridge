"""Add Intervention and Acquittement tables for HPRIM interventions/acquittements persistence

Revision ID: 2881649dd711
Revises: 4c136bb30ea9
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2881649dd711'
down_revision: Union[str, Sequence[str], None] = '4c136bb30ea9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'intervention',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dossier_id', sa.Integer(), nullable=False),
        sa.Column('identifiant', sa.String(), nullable=False),
        sa.Column('libelle', sa.String(), nullable=False),
        sa.Column('date_intervention', sa.DateTime(), nullable=False),
        sa.Column('venue_id', sa.String(), nullable=True),
        sa.Column('lieu_execution', sa.String(), nullable=True),
        sa.Column('statut', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dossier_id'], ['dossier.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'acquittement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id_original', sa.String(), nullable=False),
        sa.Column('statut', sa.String(), nullable=False),
        sa.Column('date_acquittement', sa.DateTime(), nullable=False),
        sa.Column('erreurs', sa.String(), nullable=True),
        sa.Column('avertissements', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_acquittement_message_id_original', 'acquittement', ['message_id_original'])

    op.create_table(
        'acquittementreponse',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('acquittement_id', sa.Integer(), nullable=False),
        sa.Column('identifiant_acte', sa.String(), nullable=False),
        sa.Column('type_acte', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=True),
        sa.Column('statut', sa.String(), nullable=False),
        sa.Column('code_erreur', sa.String(), nullable=True),
        sa.Column('message_erreur', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['acquittement_id'], ['acquittement.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    for table in ('ccamact', 'ngapact', 'lppact', 'ucdact'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('intervention_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f'fk_{table}_intervention_id', 'intervention', ['intervention_id'], ['id']
            )


def downgrade() -> None:
    """Downgrade schema."""
    for table in ('ccamact', 'ngapact', 'lppact', 'ucdact'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_intervention_id', type_='foreignkey')
            batch_op.drop_column('intervention_id')

    op.drop_table('acquittementreponse')
    op.drop_index('ix_acquittement_message_id_original', table_name='acquittement')
    op.drop_table('acquittement')
    op.drop_table('intervention')
