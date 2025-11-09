"""Add advanced time shifting config fields to InteropScenario.

Revision: 0004_add_scenario_time_config
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_add_scenario_time_config"
down_revision = "0003_add_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interopscenario",
        sa.Column("time_anchor_mode", sa.String(), nullable=True)
    )
    op.add_column(
        "interopscenario",
        sa.Column("time_anchor_days_offset", sa.Integer(), nullable=True)
    )
    op.add_column(
        "interopscenario",
        sa.Column("time_fixed_start_iso", sa.String(), nullable=True)
    )
    op.add_column(
        "interopscenario",
        sa.Column("preserve_intervals", sa.Boolean(), nullable=False, server_default="1")
    )
    op.add_column(
        "interopscenario",
        sa.Column("jitter_min_minutes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "interopscenario",
        sa.Column("jitter_max_minutes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "interopscenario",
        sa.Column("apply_jitter_on_events", sa.String(), nullable=True)
    )


def downgrade() -> None:
    # SQLite drop columns may fail on older versions; attempt best-effort
    try:
        op.drop_column("interopscenario", "apply_jitter_on_events")
        op.drop_column("interopscenario", "jitter_max_minutes")
        op.drop_column("interopscenario", "jitter_min_minutes")
        op.drop_column("interopscenario", "preserve_intervals")
        op.drop_column("interopscenario", "time_fixed_start_iso")
        op.drop_column("interopscenario", "time_anchor_days_offset")
        op.drop_column("interopscenario", "time_anchor_mode")
    except Exception:
        pass
