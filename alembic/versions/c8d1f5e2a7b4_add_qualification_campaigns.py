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
    with op.batch_alter_table("interopscenario") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("preconditions_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assertions_json", sa.Text(), nullable=True))

    with op.batch_alter_table("interopscenariostep") as batch_op:
        batch_op.add_column(sa.Column("assertions_json", sa.Text(), nullable=True))

    with op.batch_alter_table("scenarioexecutionrun") as batch_op:
        batch_op.add_column(sa.Column("qualification_verdict", sa.String(), nullable=False, server_default="not_evaluated"))
        batch_op.add_column(sa.Column("assertion_total", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("assertion_passed", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("evidence_json", sa.Text(), nullable=True))
        batch_op.create_index("ix_scenarioexecutionrun_qualification_verdict", ["qualification_verdict"])

    with op.batch_alter_table("scenarioexecutionsteplog") as batch_op:
        batch_op.add_column(sa.Column("assertion_results_json", sa.Text(), nullable=True))

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
    op.create_index("ix_qualificationcampaign_key", "qualificationcampaign", ["key"])
    op.create_index("ix_qualificationcampaign_is_active", "qualificationcampaign", ["is_active"])

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
        op.create_index(f"ix_qualificationcampaignitem_{column}", "qualificationcampaignitem", [column])

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
        op.create_index(f"ix_qualificationcampaignrun_{column}", "qualificationcampaignrun", [column])


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
