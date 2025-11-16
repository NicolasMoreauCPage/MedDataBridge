"""Add structural hierarchy foreign keys to IdentifierNamespace

Revision ID: 4f5a6b7c8d9e
Revises: 3da3ce50952b
Create Date: 2025-11-14 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f5a6b7c8d9e'
down_revision: Union[str, Sequence[str], None] = '3da3ce50952b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new foreign key columns for structural hierarchy
    # op.add_column('identifiernamespace', sa.Column('entite_geographique_id', sa.INTEGER(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('pole_id', sa.INTEGER(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('service_id', sa.INTEGER(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('unite_fonctionnelle_id', sa.INTEGER(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('unite_hebergement_id', sa.INTEGER(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('chambre_id', sa.INTEGER(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('lit_id', sa.INTEGER(), nullable=True))  # Already exists, skip

    # Add foreign key constraints using batch mode for SQLite compatibility
    with op.batch_alter_table('identifiernamespace') as batch_op:
        batch_op.create_foreign_key('fk_identifiernamespace_entite_geographique_id', 'entitegeographique', ['entite_geographique_id'], ['id'])
        batch_op.create_foreign_key('fk_identifiernamespace_pole_id', 'pole', ['pole_id'], ['id'])
        batch_op.create_foreign_key('fk_identifiernamespace_service_id', 'service', ['service_id'], ['id'])
        batch_op.create_foreign_key('fk_identifiernamespace_unite_fonctionnelle_id', 'unitefonctionnelle', ['unite_fonctionnelle_id'], ['id'])
        batch_op.create_foreign_key('fk_identifiernamespace_unite_hebergement_id', 'unitehebergement', ['unite_hebergement_id'], ['id'])
        batch_op.create_foreign_key('fk_identifiernamespace_chambre_id', 'chambre', ['chambre_id'], ['id'])
        batch_op.create_foreign_key('fk_identifiernamespace_lit_id', 'lit', ['lit_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraints
    op.drop_constraint('fk_identifiernamespace_lit_id', 'identifiernamespace', type_='foreignkey')
    op.drop_constraint('fk_identifiernamespace_chambre_id', 'identifiernamespace', type_='foreignkey')
    op.drop_constraint('fk_identifiernamespace_unite_hebergement_id', 'identifiernamespace', type_='foreignkey')
    op.drop_constraint('fk_identifiernamespace_unite_fonctionnelle_id', 'identifiernamespace', type_='foreignkey')
    op.drop_constraint('fk_identifiernamespace_service_id', 'identifiernamespace', type_='foreignkey')
    op.drop_constraint('fk_identifiernamespace_pole_id', 'identifiernamespace', type_='foreignkey')
    op.drop_constraint('fk_identifiernamespace_entite_geographique_id', 'identifiernamespace', type_='foreignkey')

    # Remove columns
    op.drop_column('identifiernamespace', 'lit_id')
    op.drop_column('identifiernamespace', 'chambre_id')
    op.drop_column('identifiernamespace', 'unite_hebergement_id')
    op.drop_column('identifiernamespace', 'unite_fonctionnelle_id')
    op.drop_column('identifiernamespace', 'service_id')
    op.drop_column('identifiernamespace', 'pole_id')
    op.drop_column('identifiernamespace', 'entite_geographique_id')