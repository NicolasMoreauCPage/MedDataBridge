"""Add analytics tables: OccupationSnapshot and AlertRule

Revision ID: 4c136bb30ea9
Revises: f57e7c06af2c
Create Date: 2026-01-08 08:58:57.802604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c136bb30ea9'
down_revision: Union[str, Sequence[str], None] = 'f57e7c06af2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create occupation_snapshots table
    op.create_table(
        'occupation_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('lit_id', sa.Integer(), nullable=False),
        sa.Column('is_occupied', sa.Boolean(), nullable=False, default=False),
        sa.Column('eg_id', sa.Integer(), nullable=False),
        sa.Column('uf_id', sa.Integer(), nullable=True),
        sa.Column('service_id', sa.Integer(), nullable=True),
        sa.Column('pole_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['lit_id'], ['lits.id'], ),
        sa.ForeignKeyConstraint(['eg_id'], ['entite_geographique.id'], ),
        sa.ForeignKeyConstraint(['uf_id'], ['unite_fonctionnelle.id'], ),
        sa.ForeignKeyConstraint(['service_id'], ['service.id'], ),
        sa.ForeignKeyConstraint(['pole_id'], ['pole.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_occupation_snapshots_snapshot_date', 'occupation_snapshots', ['snapshot_date'])
    op.create_index('ix_occupation_snapshots_lit_id', 'occupation_snapshots', ['lit_id'])
    op.create_index('ix_occupation_snapshots_eg_id', 'occupation_snapshots', ['eg_id'])
    
    # Create alert_rules table
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, default='medium'),
        sa.Column('eg_id', sa.Integer(), nullable=True),
        sa.Column('um_code', sa.String(length=10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['eg_id'], ['entite_geographique.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alert_rules_alert_type', 'alert_rules', ['alert_type'])
    op.create_index('ix_alert_rules_eg_id', 'alert_rules', ['eg_id'])
    op.create_index('ix_alert_rules_is_active', 'alert_rules', ['is_active'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_alert_rules_is_active', table_name='alert_rules')
    op.drop_index('ix_alert_rules_eg_id', table_name='alert_rules')
    op.drop_index('ix_alert_rules_alert_type', table_name='alert_rules')
    op.drop_table('alert_rules')
    
    op.drop_index('ix_occupation_snapshots_eg_id', table_name='occupation_snapshots')
    op.drop_index('ix_occupation_snapshots_lit_id', table_name='occupation_snapshots')
    op.drop_index('ix_occupation_snapshots_snapshot_date', table_name='occupation_snapshots')
    op.drop_table('occupation_snapshots')
