"""Make qualification campaign runs resumable.

Revision ID: fa7d1e4c9b20
Revises: f8b2c0d9e1a6
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "fa7d1e4c9b20"
down_revision = "f8b2c0d9e1a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("qualificationcampaignrun")}
    additions = (
        ("dry_run", sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("next_item_index", sa.Column("next_item_index", sa.Integer(), nullable=False, server_default="0")),
        ("error_message", sa.Column("error_message", sa.Text(), nullable=True)),
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("qualificationcampaignrun", column)


def downgrade() -> None:
    # Les preuves de campagne sont conservées lors d'un retour arrière.
    pass
