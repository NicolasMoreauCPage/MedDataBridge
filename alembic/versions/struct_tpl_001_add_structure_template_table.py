"""add_structure_template_table

Revision ID: struct_tpl_001
Revises: 
Create Date: 2026-01-08

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'struct_tpl_001'
down_revision = None  # Will be manually linked
branch_labels = None
depends_on = None


def upgrade():
    # Create structuretemplate table
    op.create_table(
        'structuretemplate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('template_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('payload', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_structuretemplate_key'), 'structuretemplate', ['key'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_structuretemplate_key'), table_name='structuretemplate')
    op.drop_table('structuretemplate')
