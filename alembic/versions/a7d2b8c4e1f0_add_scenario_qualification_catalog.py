"""Add scenario catalogue qualification, themes and target states.

Revision ID: a7d2b8c4e1f0
Revises: f6c8e2a1d4b9
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "a7d2b8c4e1f0"
down_revision = "f6c8e2a1d4b9"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {item["name"] for item in sa.inspect(bind).get_columns(table)}


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "interopscenario")
    for name, column in (
        ("functional_comment", sa.Column("functional_comment", sa.Text(), nullable=True)),
        ("source_checksum", sa.Column("source_checksum", sa.String(), nullable=True)),
        ("legacy_package", sa.Column("legacy_package", sa.String(), nullable=True)),
        ("legacy_source_json", sa.Column("legacy_source_json", sa.Text(), nullable=True)),
    ):
        if name not in columns:
            op.add_column("interopscenario", column)
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("interopscenario")}
    for name, column in (("ix_interopscenario_source_checksum", "source_checksum"), ("ix_interopscenario_legacy_package", "legacy_package")):
        if name not in indexes:
            op.create_index(name, "interopscenario", [column])

    tables = _tables(bind)
    if "scenariotheme" not in tables:
        op.create_table(
            "scenariotheme",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(), nullable=False, unique=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("scenariotheme.id"), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        for column in ("key", "parent_id", "order_index", "is_active"):
            op.create_index(f"ix_scenariotheme_{column}", "scenariotheme", [column])
    if "scenariothemeassignment" not in tables:
        op.create_table(
            "scenariothemeassignment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("interopscenario.id"), nullable=False),
            sa.Column("theme_id", sa.Integer(), sa.ForeignKey("scenariotheme.id"), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("scenario_id", "theme_id", name="uq_scenario_theme_assignment"),
        )
        for column in ("scenario_id", "theme_id", "is_primary"):
            op.create_index(f"ix_scenariothemeassignment_{column}", "scenariothemeassignment", [column])
    if "scenariotargetstate" not in tables:
        op.create_table(
            "scenariotargetstate",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("interopscenario.id"), nullable=False),
            sa.Column("target_system_key", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(), nullable=False, server_default="never_run"),
            sa.Column("status_since", sa.DateTime(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_success_at", sa.DateTime(), nullable=True),
            sa.Column("last_failure_at", sa.DateTime(), nullable=True),
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_play_id", sa.Integer(), sa.ForeignKey("scenarioplay.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("scenario_id", "target_system_key", name="uq_scenario_target_state"),
        )
        for column in ("scenario_id", "target_system_key", "is_active", "status", "status_since", "last_run_at", "last_success_at", "last_failure_at", "last_play_id"):
            op.create_index(f"ix_scenariotargetstate_{column}", "scenariotargetstate", [column])

    if "qualificationcampaign" in tables and "target_system_key" not in _columns(bind, "qualificationcampaign"):
        op.add_column("qualificationcampaign", sa.Column("target_system_key", sa.String(), nullable=True))
        op.create_index("ix_qualificationcampaign_target_system_key", "qualificationcampaign", ["target_system_key"])


def downgrade() -> None:
    # Downgrade is intentionally conservative: qualification history can be
    # material evidence and must not be silently deleted.
    pass
