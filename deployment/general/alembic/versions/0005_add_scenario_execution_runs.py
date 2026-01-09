"""add scenario execution run models

Revision ID: 0005_add_scenario_execution_runs
Revises: 0004_add_scenario_time_config
Create Date: 2025-11-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_add_scenario_execution_runs"
down_revision = "0004_add_scenario_time_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "scenarioexecutionrun" not in existing:
        op.create_table(
            "scenarioexecutionrun",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("interopscenario.id"), nullable=False, index=True),
            sa.Column("endpoint_id", sa.Integer(), sa.ForeignKey("systemendpoint.id"), nullable=True, index=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True, index=True),
            sa.Column("status", sa.String(), nullable=False, index=True),
            sa.Column("total_steps", sa.Integer(), nullable=False, default=0),
            sa.Column("success_steps", sa.Integer(), nullable=False, default=0),
            sa.Column("error_steps", sa.Integer(), nullable=False, default=0),
            sa.Column("skipped_steps", sa.Integer(), nullable=False, default=0),
            sa.Column("dry_run", sa.Boolean(), nullable=False, default=False, index=True),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "scenarioexecutionsteplog" not in existing:
        op.create_table(
            "scenarioexecutionsteplog",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("scenarioexecutionrun.id"), nullable=False, index=True),
            sa.Column("step_id", sa.Integer(), sa.ForeignKey("interopscenariostep.id"), nullable=True, index=True),
            sa.Column("endpoint_id", sa.Integer(), sa.ForeignKey("systemendpoint.id"), nullable=True, index=True),
            sa.Column("order_index", sa.Integer(), nullable=True, index=True),
            sa.Column("status", sa.String(), nullable=False, index=True),
            sa.Column("ack_code", sa.String(), nullable=True, index=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("payload_excerpt", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    # Index composites (créer seulement si table existe et index absent)
    if "scenarioexecutionrun" in existing:
        # Vérifier si index déjà présent
        run_indexes = [i['name'] for i in inspector.get_indexes('scenarioexecutionrun')]
        if "ix_run_scenario_status" not in run_indexes:
            op.create_index("ix_run_scenario_status", "scenarioexecutionrun", ["scenario_id", "status"])
    if "scenarioexecutionsteplog" in existing:
        step_indexes = [i['name'] for i in inspector.get_indexes('scenarioexecutionsteplog')]
        if "ix_step_run_status" not in step_indexes:
            op.create_index("ix_step_run_status", "scenarioexecutionsteplog", ["run_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_step_run_status", table_name="scenarioexecutionsteplog")
    op.drop_index("ix_run_scenario_status", table_name="scenarioexecutionrun")
    op.drop_table("scenarioexecutionsteplog")
    op.drop_table("scenarioexecutionrun")
