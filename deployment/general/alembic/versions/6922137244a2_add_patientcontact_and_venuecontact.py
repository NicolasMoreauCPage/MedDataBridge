"""Add PatientContact and VenueContact tables for NK1 contacts.

Manual migration because autogenerate template missing previously.

Revision ID: 6922137244a2
Revises: 0005_add_scenario_execution_runs
Create Date: 2025-11-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6922137244a2'
down_revision = '0005_add_scenario_execution_runs'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'patient_contact' not in existing:
        op.create_table(
            'patient_contact',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patient.id'), nullable=False),
            sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('family_name', sa.String(length=100), nullable=False),
            sa.Column('given_name', sa.String(length=100)),
            sa.Column('middle_name', sa.String(length=100)),
            sa.Column('prefix', sa.String(length=20)),
            sa.Column('suffix', sa.String(length=20)),
            sa.Column('relationship_code', sa.String(length=20), nullable=False),
            sa.Column('relationship_display', sa.String(length=100)),
            sa.Column('relationship_system', sa.String(length=50), server_default='HL7-0063'),
            sa.Column('address_line1', sa.String(length=200)),
            sa.Column('address_line2', sa.String(length=200)),
            sa.Column('address_city', sa.String(length=100)),
            sa.Column('address_postalcode', sa.String(length=20)),
            sa.Column('address_country', sa.String(length=3), server_default='FR'),
            sa.Column('phone_number', sa.String(length=50)),
            sa.Column('phone_use', sa.String(length=20), server_default='home'),
            sa.Column('business_phone', sa.String(length=50)),
            sa.Column('contact_role', sa.String(length=50)),
            sa.Column('start_date', sa.Date()),
            sa.Column('end_date', sa.Date()),
            sa.Column('gender', sa.String(length=1)),
            sa.Column('birth_date', sa.Date()),
            sa.Column('primary_language', sa.String(length=10)),
            sa.Column('contact_reason', sa.String(length=200)),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('is_emergency_contact', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column('updated_at', sa.DateTime()),
        )
        op.create_index('ix_patient_contact_patient_id', 'patient_contact', ['patient_id'])
        op.create_index('ix_patient_contact_priority', 'patient_contact', ['priority'])

    if 'venue_contact' not in existing:
        op.create_table(
            'venue_contact',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('venue_id', sa.Integer(), sa.ForeignKey('venue.id'), nullable=False),
            sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('family_name', sa.String(length=100), nullable=False),
            sa.Column('given_name', sa.String(length=100)),
            sa.Column('middle_name', sa.String(length=100)),
            sa.Column('prefix', sa.String(length=20)),
            sa.Column('suffix', sa.String(length=20)),
            sa.Column('relationship_code', sa.String(length=20), nullable=False),
            sa.Column('relationship_display', sa.String(length=100)),
            sa.Column('relationship_system', sa.String(length=50), server_default='HL7-0063'),
            sa.Column('address_line1', sa.String(length=200)),
            sa.Column('address_line2', sa.String(length=200)),
            sa.Column('address_city', sa.String(length=100)),
            sa.Column('address_postalcode', sa.String(length=20)),
            sa.Column('address_country', sa.String(length=3), server_default='FR'),
            sa.Column('phone_number', sa.String(length=50)),
            sa.Column('phone_use', sa.String(length=20), server_default='home'),
            sa.Column('business_phone', sa.String(length=50)),
            sa.Column('contact_role', sa.String(length=50)),
            sa.Column('start_datetime', sa.DateTime()),
            sa.Column('end_datetime', sa.DateTime()),
            sa.Column('gender', sa.String(length=1)),
            sa.Column('birth_date', sa.Date()),
            sa.Column('contact_reason', sa.String(length=200)),
            sa.Column('is_accompanying', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('can_visit', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('notification_required', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column('updated_at', sa.DateTime()),
        )
        op.create_index('ix_venue_contact_venue_id', 'venue_contact', ['venue_id'])
        op.create_index('ix_venue_contact_is_accompanying', 'venue_contact', ['is_accompanying'])

def downgrade():
    op.drop_index('ix_venue_contact_is_accompanying', table_name='venue_contact')
    op.drop_index('ix_venue_contact_venue_id', table_name='venue_contact')
    op.drop_table('venue_contact')
    op.drop_index('ix_patient_contact_priority', table_name='patient_contact')
    op.drop_index('ix_patient_contact_patient_id', table_name='patient_contact')
    op.drop_table('patient_contact')
