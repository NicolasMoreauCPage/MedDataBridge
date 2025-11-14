"""Make identifiernamespace.name nullable

Revision ID: 3da3ce50952b
Revises: 6922137244a2
Create Date: 2025-11-14 18:42:27.733621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3da3ce50952b'
down_revision: Union[str, Sequence[str], None] = '6922137244a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # For SQLite, we need to recreate the table to make a column nullable
    # First, rename the existing table
    op.rename_table('identifiernamespace', 'identifiernamespace_old')

    # Create new table with nullable name column
    op.create_table('identifiernamespace',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('name', sa.VARCHAR(), nullable=True),  # Made nullable
        sa.Column('system', sa.VARCHAR(), nullable=True),
        sa.Column('oid', sa.VARCHAR(), nullable=True),
        sa.Column('type', sa.VARCHAR(), nullable=True),
        sa.Column('description', sa.VARCHAR(), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=True),
        sa.Column('prefix_pattern', sa.VARCHAR(), nullable=True),
        sa.Column('prefix_mode', sa.VARCHAR(), nullable=True),
        sa.Column('prefix_min', sa.INTEGER(), nullable=True),
        sa.Column('prefix_max', sa.INTEGER(), nullable=True),
        sa.Column('created_at', sa.DATETIME(), nullable=True),
        sa.Column('updated_at', sa.DATETIME(), nullable=True),
        sa.Column('ght_context_id', sa.INTEGER(), nullable=True),
        sa.Column('entite_juridique_id', sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(['ght_context_id'], ['ghtcontext.id']),
        sa.ForeignKeyConstraint(['entite_juridique_id'], ['entitejuridique.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy all data from old table to new table
    op.execute('''
        INSERT INTO identifiernamespace
        (id, name, system, oid, type, description, is_active, prefix_pattern,
         prefix_mode, prefix_min, prefix_max, created_at, updated_at,
         ght_context_id, entite_juridique_id)
        SELECT id, name, system, oid, type, description, is_active, prefix_pattern,
               prefix_mode, prefix_min, prefix_max, created_at, updated_at,
               ght_context_id, entite_juridique_id
        FROM identifiernamespace_old
    ''')

    # Drop the old table
    op.drop_table('identifiernamespace_old')


def downgrade() -> None:
    """Downgrade schema."""
    # For downgrade, we need to make name NOT NULL again
    # First, rename the existing table
    op.rename_table('identifiernamespace', 'identifiernamespace_old')

    # Create new table with non-nullable name column
    op.create_table('identifiernamespace',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('name', sa.VARCHAR(), nullable=False),  # Made non-nullable
        sa.Column('system', sa.VARCHAR(), nullable=True),
        sa.Column('oid', sa.VARCHAR(), nullable=True),
        sa.Column('type', sa.VARCHAR(), nullable=True),
        sa.Column('description', sa.VARCHAR(), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=True),
        sa.Column('prefix_pattern', sa.VARCHAR(), nullable=True),
        sa.Column('prefix_mode', sa.VARCHAR(), nullable=True),
        sa.Column('prefix_min', sa.INTEGER(), nullable=True),
        sa.Column('prefix_max', sa.INTEGER(), nullable=True),
        sa.Column('created_at', sa.DATETIME(), nullable=True),
        sa.Column('updated_at', sa.DATETIME(), nullable=True),
        sa.Column('ght_context_id', sa.INTEGER(), nullable=True),
        sa.Column('entite_juridique_id', sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(['ght_context_id'], ['ghtcontext.id']),
        sa.ForeignKeyConstraint(['entite_juridique_id'], ['entitejuridique.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from old table to new table, but only where name is not null
    op.execute('''
        INSERT INTO identifiernamespace
        (id, name, system, oid, type, description, is_active, prefix_pattern,
         prefix_mode, prefix_min, prefix_max, created_at, updated_at,
         ght_context_id, entite_juridique_id)
        SELECT id, name, system, oid, type, description, is_active, prefix_pattern,
               prefix_mode, prefix_min, prefix_max, created_at, updated_at,
               ght_context_id, entite_juridique_id
        FROM identifiernamespace_old
        WHERE name IS NOT NULL
    ''')

    # Drop the old table
    op.drop_table('identifiernamespace_old')
