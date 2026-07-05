"""add french extension segments (ZFD/ZFA/ZFP/ZFV) fields

Revision ID: a1f3e9c02b7d
Revises: 2881649dd711
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f3e9c02b7d'
down_revision: Union[str, Sequence[str], None] = '2881649dd711'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('patient') as batch_op:
        # Segment ZFD (complément démographique)
        batch_op.add_column(sa.Column('sms_consent', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('birth_date_modified_indicator', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('identity_capture_mode', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('identity_proof_type', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('identity_proof_expiry_date', sa.Date(), nullable=True))
        # Segment ZFA (statut DMP / Espace Santé)
        batch_op.add_column(sa.Column('dmp_status', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('dmp_status_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('dmp_closure_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('dmp_feed_opposition', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('dmp_consultation_consent', sa.String(), nullable=True))
        # Segment ZFP (situation professionnelle)
        batch_op.add_column(sa.Column('socio_professional_activity', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('socio_professional_category', sa.String(), nullable=True))

    with op.batch_alter_table('mouvement') as batch_op:
        # Segment ZFV (compléments sur la rencontre)
        batch_op.add_column(sa.Column('origin_facility_finess', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('origin_stay_date', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('discharge_transport_mode', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('legal_care_mode_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('transport_care_level', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('mouvement') as batch_op:
        batch_op.drop_column('transport_care_level')
        batch_op.drop_column('legal_care_mode_code')
        batch_op.drop_column('discharge_transport_mode')
        batch_op.drop_column('origin_stay_date')
        batch_op.drop_column('origin_facility_finess')

    with op.batch_alter_table('patient') as batch_op:
        batch_op.drop_column('socio_professional_category')
        batch_op.drop_column('socio_professional_activity')
        batch_op.drop_column('dmp_consultation_consent')
        batch_op.drop_column('dmp_feed_opposition')
        batch_op.drop_column('dmp_closure_date')
        batch_op.drop_column('dmp_status_date')
        batch_op.drop_column('dmp_status')
        batch_op.drop_column('identity_proof_expiry_date')
        batch_op.drop_column('identity_proof_type')
        batch_op.drop_column('identity_capture_mode')
        batch_op.drop_column('birth_date_modified_indicator')
        batch_op.drop_column('sms_consent')
