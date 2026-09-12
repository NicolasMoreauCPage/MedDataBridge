"""Add durable scenario delivery links and immutable scenario versions.

Revision ID: c3f91a0d6e25
Revises: a7d2b8c4e1f0
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "c3f91a0d6e25"
down_revision = "a7d2b8c4e1f0"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {item["name"] for item in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {item["name"] for item in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "scenarioversion" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "scenarioversion",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("interopscenario.id"), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("content_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("content_checksum", sa.String(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("scenario_id", "version_number", name="uq_scenario_version_number"),
        )
        for col in ("scenario_id", "version_number", "status", "content_checksum", "published_at"):
            op.create_index(f"ix_scenarioversion_{col}", "scenarioversion", [col])

    cols = _columns(bind, "interopscenario")
    if "current_version_id" not in cols:
        op.add_column("interopscenario", sa.Column("current_version_id", sa.Integer(), nullable=True))
        op.create_index("ix_interopscenario_current_version_id", "interopscenario", ["current_version_id"])

    cols = _columns(bind, "scenarioplay")
    if "scenario_version_id" not in cols:
        # SQLite ne sait pas ajouter une contrainte FK par ALTER TABLE ; les
        # références applicatives restent contrôlées par SQLModel et les
        # installations neuves reçoivent bien la FK via le modèle complet.
        op.add_column("scenarioplay", sa.Column("scenario_version_id", sa.Integer(), nullable=True))
        op.create_index("ix_scenarioplay_scenario_version_id", "scenarioplay", ["scenario_version_id"])
    if "error_policy" not in cols:
        op.add_column("scenarioplay", sa.Column("error_policy", sa.String(), nullable=False, server_default="continue_other_targets"))
        op.create_index("ix_scenarioplay_error_policy", "scenarioplay", ["error_policy"])

    cols = _columns(bind, "scenariodelivery")
    if "outbox_id" not in cols:
        op.add_column("scenariodelivery", sa.Column("outbox_id", sa.Integer(), nullable=True))
        op.create_index("ix_scenariodelivery_outbox_id", "scenariodelivery", ["outbox_id"])

    cols = _columns(bind, "outboundmessage")
    if "scenario_delivery_id" not in cols:
        op.add_column("outboundmessage", sa.Column("scenario_delivery_id", sa.Integer(), nullable=True))
        op.create_index("ix_outboundmessage_scenario_delivery_id", "outboundmessage", ["scenario_delivery_id"])
        op.create_index("uq_outboundmessage_scenario_delivery", "outboundmessage", ["scenario_delivery_id"], unique=True)
    if "response_payload" not in cols:
        op.add_column("outboundmessage", sa.Column("response_payload", sa.Text(), nullable=True))


def downgrade() -> None:
    # Historical evidence must not be deleted by a downgrade.
    pass
