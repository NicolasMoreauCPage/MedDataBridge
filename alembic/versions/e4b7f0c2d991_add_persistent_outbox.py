"""Add persistent outbound message queue.

Revision ID: e4b7f0c2d991
Revises: c8d1f5e2a7b4
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "e4b7f0c2d991"
down_revision = "c8d1f5e2a7b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "outboundmessage" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "outboundmessage",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("endpoint_id", sa.Integer(), sa.ForeignKey("systemendpoint.id"), nullable=False),
            sa.Column("source_message_log_id", sa.Integer(), sa.ForeignKey("messagelog.id"), nullable=True),
            sa.Column("protocol", sa.String(), nullable=False),
            sa.Column("message_type", sa.String(), nullable=True),
            sa.Column("correlation_id", sa.String(), nullable=True),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
            sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
        )
    existing = {idx["name"] for idx in sa.inspect(bind).get_indexes("outboundmessage")}
    for name, columns in {
        "ix_outboundmessage_endpoint_id": ["endpoint_id"],
        "ix_outboundmessage_source_message_log_id": ["source_message_log_id"],
        "ix_outboundmessage_protocol": ["protocol"],
        "ix_outboundmessage_correlation_id": ["correlation_id"],
        "ix_outboundmessage_status": ["status"],
        "ix_outboundmessage_next_attempt_at": ["next_attempt_at"],
    }.items():
        if name not in existing:
            op.create_index(name, "outboundmessage", columns)


def downgrade() -> None:
    op.drop_table("outboundmessage")
