"""Add immutable multi-protocol scenario plays.

Revision ID: f6c8e2a1d4b9
Revises: e4b7f0c2d991
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "f6c8e2a1d4b9"
down_revision = "e4b7f0c2d991"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {item["name"] for item in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "systemendpoint", "target_system_key"):
        op.add_column("systemendpoint", sa.Column("target_system_key", sa.String(), nullable=True))
        op.create_index("ix_systemendpoint_target_system_key", "systemendpoint", ["target_system_key"])

    if "scenarioplay" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "scenarioplay",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("interopscenario.id"), nullable=False),
            sa.Column("play_key", sa.String(), nullable=False, unique=True),
            sa.Column("ght_context_id", sa.Integer(), sa.ForeignKey("ghtcontext.id"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="prepared"),
            sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("identity_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        for column in ("scenario_id", "play_key", "ght_context_id", "status", "dry_run", "started_at", "finished_at"):
            op.create_index(f"ix_scenarioplay_{column}", "scenarioplay", [column])
    if "scenarioplaytarget" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "scenarioplaytarget",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("play_id", sa.Integer(), sa.ForeignKey("scenarioplay.id"), nullable=False),
            sa.Column("endpoint_id", sa.Integer(), sa.ForeignKey("systemendpoint.id"), nullable=False),
            sa.Column("target_system_key", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("play_id", "endpoint_id", name="uq_scenario_play_target"),
        )
        for column in ("play_id", "endpoint_id", "target_system_key", "status"):
            op.create_index(f"ix_scenarioplaytarget_{column}", "scenarioplaytarget", [column])
    if "scenarioplaystep" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "scenarioplaystep",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("play_id", sa.Integer(), sa.ForeignKey("scenarioplay.id"), nullable=False),
            sa.Column("scenario_step_id", sa.Integer(), sa.ForeignKey("interopscenariostep.id"), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=True), sa.Column("message_format", sa.String(), nullable=False),
            sa.Column("message_type", sa.String(), nullable=True), sa.Column("source_payload", sa.Text(), nullable=False),
            sa.Column("compiled_payload", sa.Text(), nullable=False), sa.Column("routing_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("play_id", "order_index", name="uq_scenario_play_step_order"),
        )
        for column in ("play_id", "scenario_step_id", "order_index", "message_format"):
            op.create_index(f"ix_scenarioplaystep_{column}", "scenarioplaystep", [column])
    if "scenariodelivery" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "scenariodelivery",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("play_id", sa.Integer(), sa.ForeignKey("scenarioplay.id"), nullable=False),
            sa.Column("play_step_id", sa.Integer(), sa.ForeignKey("scenarioplaystep.id"), nullable=False),
            sa.Column("endpoint_id", sa.Integer(), sa.ForeignKey("systemendpoint.id"), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"), sa.Column("transport", sa.String(), nullable=True),
            sa.Column("ack_code", sa.String(), nullable=True), sa.Column("response_payload", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True), sa.Column("message_log_id", sa.Integer(), sa.ForeignKey("messagelog.id"), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True), sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("play_step_id", "endpoint_id", name="uq_scenario_delivery_step_endpoint"),
        )
        for column in ("play_id", "play_step_id", "endpoint_id", "status", "transport", "message_log_id"):
            op.create_index(f"ix_scenariodelivery_{column}", "scenariodelivery", [column])


def downgrade() -> None:
    op.drop_table("scenariodelivery")
    op.drop_table("scenarioplaystep")
    op.drop_table("scenarioplaytarget")
    op.drop_table("scenarioplay")
    op.drop_index("ix_systemendpoint_target_system_key", table_name="systemendpoint")
    op.drop_column("systemendpoint", "target_system_key")
