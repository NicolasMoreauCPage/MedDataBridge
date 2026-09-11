"""Add qualification assertions and campaign execution tables.

Revision ID: c8d1f5e2a7b4
Revises: b2e4f0a13c9e
Create Date: 2026-08-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c8d1f5e2a7b4"
down_revision = "b2e4f0a13c9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply safely to databases initialized by older ``create_all`` startup paths.

    Those databases can already contain the campaign tables but still miss the
    additive columns below. Alembic normally sees a pristine predecessor schema;
    inspecting first makes the migration safely resumable for existing installs.
    """
    bind = op.get_bind()

    def table_exists(name: str) -> bool:
        return name in sa.inspect(bind).get_table_names()

    def add_missing_columns(table: str, columns: list[sa.Column]) -> None:
        existing = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        missing = [column for column in columns if column.name not in existing]
        if missing:
            with op.batch_alter_table(table) as batch_op:
                for column in missing:
                    batch_op.add_column(column)

    def ensure_index(name: str, table: str, columns: list[str]) -> None:
        existing = {index["name"] for index in sa.inspect(bind).get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, columns)

    add_missing_columns(
        "interopscenario",
        [
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("preconditions_json", sa.Text(), nullable=True),
            sa.Column("assertions_json", sa.Text(), nullable=True),
        ],
    )
    add_missing_columns(
        "interopscenariostep",
        [sa.Column("assertions_json", sa.Text(), nullable=True)],
    )
    add_missing_columns(
        "scenarioexecutionrun",
        [
            sa.Column("qualification_verdict", sa.String(), nullable=False, server_default="not_evaluated"),
            sa.Column("assertion_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("assertion_passed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("evidence_json", sa.Text(), nullable=True),
        ],
    )
    ensure_index("ix_scenarioexecutionrun_qualification_verdict", "scenarioexecutionrun", ["qualification_verdict"])
    add_missing_columns(
        "scenarioexecutionsteplog",
        [sa.Column("assertion_results_json", sa.Text(), nullable=True)],
    )

    if not table_exists("qualificationcampaign"):
        op.create_table(
        "qualificationcampaign",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("profile", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        )
    ensure_index("ix_qualificationcampaign_key", "qualificationcampaign", ["key"])
    ensure_index("ix_qualificationcampaign_is_active", "qualificationcampaign", ["is_active"])

    if not table_exists("qualificationcampaignitem"):
        op.create_table(
        "qualificationcampaignitem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("endpoint_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["qualificationcampaign.id"]),
        sa.ForeignKeyConstraint(["scenario_id"], ["interopscenario.id"]),
        sa.ForeignKeyConstraint(["endpoint_id"], ["systemendpoint.id"]),
        sa.PrimaryKeyConstraint("id"),
        )
    for column in ("campaign_id", "scenario_id", "endpoint_id", "order_index", "is_active"):
        ensure_index(f"ix_qualificationcampaignitem_{column}", "qualificationcampaignitem", [column])

    if not table_exists("qualificationcampaignrun"):
        op.create_table(
        "qualificationcampaignrun",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("passed_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["qualificationcampaign.id"]),
        sa.PrimaryKeyConstraint("id"),
        )
    for column in ("campaign_id", "finished_at", "status"):
        ensure_index(f"ix_qualificationcampaignrun_{column}", "qualificationcampaignrun", [column])


def downgrade() -> None:
    for column in ("status", "finished_at", "campaign_id"):
        op.drop_index(f"ix_qualificationcampaignrun_{column}", table_name="qualificationcampaignrun")
    op.drop_table("qualificationcampaignrun")
    for column in ("is_active", "order_index", "endpoint_id", "scenario_id", "campaign_id"):
        op.drop_index(f"ix_qualificationcampaignitem_{column}", table_name="qualificationcampaignitem")
    op.drop_table("qualificationcampaignitem")
    op.drop_index("ix_qualificationcampaign_is_active", table_name="qualificationcampaign")
    op.drop_index("ix_qualificationcampaign_key", table_name="qualificationcampaign")
    op.drop_table("qualificationcampaign")
    with op.batch_alter_table("scenarioexecutionsteplog") as batch_op:
        batch_op.drop_column("assertion_results_json")
    with op.batch_alter_table("scenarioexecutionrun") as batch_op:
        batch_op.drop_index("ix_scenarioexecutionrun_qualification_verdict")
        batch_op.drop_column("evidence_json")
        batch_op.drop_column("assertion_passed")
        batch_op.drop_column("assertion_total")
        batch_op.drop_column("qualification_verdict")
    with op.batch_alter_table("interopscenariostep") as batch_op:
        batch_op.drop_column("assertions_json")
    with op.batch_alter_table("interopscenario") as batch_op:
        batch_op.drop_column("assertions_json")
        batch_op.drop_column("preconditions_json")
        batch_op.drop_column("version")
