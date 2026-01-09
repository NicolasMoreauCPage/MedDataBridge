"""add_medecin_responsable_table_and_relations

Revision ID: 5fc898b68be8
Revises: 0008_add_namespace_hierarchy_columns
Create Date: 2025-12-06 08:52:43.294525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5fc898b68be8'
down_revision: Union[str, Sequence[str], None] = '0008_add_namespace_hierarchy_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Créer la table medecinresponsable
    op.create_table('medecinresponsable',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rpps', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('adeli', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('family_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('given_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('middle_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('prefix', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('suffix', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('specialty', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_medecinresponsable_adeli'), 'medecinresponsable', ['adeli'], unique=False)
    op.create_index(op.f('ix_medecinresponsable_rpps'), 'medecinresponsable', ['rpps'], unique=False)
    
    # Ajouter medecin_responsable_id aux tables avec batch mode pour SQLite
    with op.batch_alter_table('dossier', schema=None) as batch_op:
        batch_op.add_column(sa.Column('medecin_responsable_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('mouvement', schema=None) as batch_op:
        batch_op.add_column(sa.Column('medecin_responsable_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('unitefonctionnelle', schema=None) as batch_op:
        batch_op.add_column(sa.Column('medecin_responsable_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Supprimer les colonnes medecin_responsable_id
    with op.batch_alter_table('unitefonctionnelle', schema=None) as batch_op:
        batch_op.drop_column('medecin_responsable_id')
    
    with op.batch_alter_table('mouvement', schema=None) as batch_op:
        batch_op.drop_column('medecin_responsable_id')
    
    with op.batch_alter_table('dossier', schema=None) as batch_op:
        batch_op.drop_column('medecin_responsable_id')
    
    # Supprimer la table medecinresponsable
    op.drop_index(op.f('ix_medecinresponsable_rpps'), table_name='medecinresponsable')
    op.drop_index(op.f('ix_medecinresponsable_adeli'), table_name='medecinresponsable')
    op.drop_table('medecinresponsable')
