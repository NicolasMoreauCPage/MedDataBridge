"""Merge heads 2025-12-05

Revision ID: merge_heads_20251205
Revises: 0006_add_scenario_ej_config, f921c9819703
Create Date: 2025-12-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "merge_heads_20251205"
down_revision = ("0006_add_scenario_ej_config", "f921c9819703")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge heads - no actual changes needed."""
    pass


def downgrade() -> None:
    """Reverse merge - no actual changes needed."""
    pass
