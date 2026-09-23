"""Add the expected outcome contract to the scenario catalogue.

Revision ID: f8b2c0d9e1a6
Revises: e5f0a92b7cd0
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "f8b2c0d9e1a6"
down_revision = "e5f0a92b7cd0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("interopscenario")}
    if "expected_outcome_json" not in columns:
        op.add_column("interopscenario", sa.Column("expected_outcome_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # Le catalogue est une donnée de référence et peut avoir été enrichi
    # localement : aucun effacement automatique ne doit supprimer ce travail.
    pass
