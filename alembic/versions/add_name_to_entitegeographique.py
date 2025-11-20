"""
Revision ID: add_name_to_entitegeographique
Revises: 6922137244a2
Create Date: 2025-11-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_name_to_entitegeographique'
down_revision = '6922137244a2'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('entitegeographique')]
    if 'name' not in columns:
        op.add_column('entitegeographique', sa.Column('name', sa.String(), nullable=True))

def downgrade():
    op.drop_column('entitegeographique', 'name')
