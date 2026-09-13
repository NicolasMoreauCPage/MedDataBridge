"""Add durable scenario routing, validation and scheduling metadata.

Revision ID: b6d4e2f7a901
Revises: fa7d1e4c9b20
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa


revision = "b6d4e2f7a901"
down_revision = "fa7d1e4c9b20"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    columns = _columns("interopscenariostep")
    additions = (
        ("is_required", sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("route_mode", sa.Column("route_mode", sa.String(), nullable=False, server_default="all_compatible")),
        ("endpoint_ids_json", sa.Column("endpoint_ids_json", sa.Text(), nullable=True)),
        ("target_system_key", sa.Column("target_system_key", sa.String(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("interopscenariostep", column)
    op.create_index("ix_interopscenariostep_target_system_key", "interopscenariostep", ["target_system_key"], unique=False)

    columns = _columns("scenarioplaytarget")
    if "is_required" not in columns:
        op.add_column("scenarioplaytarget", sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_scenarioplaytarget_is_required", "scenarioplaytarget", ["is_required"], unique=False)

    columns = _columns("scenarioplaystep")
    if "delay_seconds" not in columns:
        op.add_column("scenarioplaystep", sa.Column("delay_seconds", sa.Integer(), nullable=False, server_default="0"))

    columns = _columns("scenariodelivery")
    additions = (
        ("is_required", sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("scheduled_at", sa.Column("scheduled_at", sa.DateTime(), nullable=True)),
        ("validation_status", sa.Column("validation_status", sa.String(), nullable=True)),
        ("validation_json", sa.Column("validation_json", sa.Text(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("scenariodelivery", column)
    op.create_index("ix_scenariodelivery_is_required", "scenariodelivery", ["is_required"], unique=False)
    op.create_index("ix_scenariodelivery_scheduled_at", "scenariodelivery", ["scheduled_at"], unique=False)
    op.create_index("ix_scenariodelivery_validation_status", "scenariodelivery", ["validation_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scenariodelivery_validation_status", table_name="scenariodelivery")
    op.drop_index("ix_scenariodelivery_scheduled_at", table_name="scenariodelivery")
    op.drop_index("ix_scenariodelivery_is_required", table_name="scenariodelivery")
    for name in ("validation_json", "validation_status", "scheduled_at", "is_required"):
        op.drop_column("scenariodelivery", name)
    op.drop_column("scenarioplaystep", "delay_seconds")
    op.drop_index("ix_scenarioplaytarget_is_required", table_name="scenarioplaytarget")
    op.drop_column("scenarioplaytarget", "is_required")
    op.drop_index("ix_interopscenariostep_target_system_key", table_name="interopscenariostep")
    for name in ("target_system_key", "endpoint_ids_json", "route_mode", "is_required"):
        op.drop_column("interopscenariostep", name)
