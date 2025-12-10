"""
Revision ID: merge_heads_20251116
Revises: 4f5a6b7c8d9e, add_name_to_entitegeographique
Create Date: 2025-11-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_heads_20251116'
down_revision = ('4f5a6b7c8d9e', 'add_name_to_entitegeographique')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
