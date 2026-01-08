"""
Revision ID: add_created_updated_to_identifiernamespace
Revises: merge_heads_20251116
Create Date: 2025-11-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_created_updated_to_identifiernamespace'
down_revision = 'merge_heads_20251116'
branch_labels = None
depends_on = None

def upgrade():
    # op.add_column('identifiernamespace', sa.Column('created_at', sa.DateTime(), nullable=True))  # Already exists, skip
    # op.add_column('identifiernamespace', sa.Column('updated_at', sa.DateTime(), nullable=True))  # Already exists, skip
    pass
def downgrade():
    op.drop_column('identifiernamespace', 'created_at')
    op.drop_column('identifiernamespace', 'updated_at')
