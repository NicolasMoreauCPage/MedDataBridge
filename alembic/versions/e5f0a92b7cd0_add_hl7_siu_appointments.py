"""Add persistent HL7 v2 SIU appointments.

Revision ID: e5f0a92b7cd0
Revises: d4a82b0e7f31
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "e5f0a92b7cd0"
down_revision = "d4a82b0e7f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "appointment" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "appointment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("assigning_authority", sa.String(), nullable=False, server_default=""),
        sa.Column("patient_identifier", sa.String(), nullable=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="booked"),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("service_code", sa.String(), nullable=True),
        sa.Column("location_code", sa.String(), nullable=True),
        sa.Column("practitioner_identifier", sa.String(), nullable=True),
        sa.Column("last_trigger", sa.String(), nullable=False, server_default="S12"),
        sa.Column("source_endpoint_id", sa.Integer(), sa.ForeignKey("systemendpoint.id"), nullable=True),
        sa.Column("source_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("external_id", "assigning_authority", name="uq_appointment_external_authority"),
    )
    for column in ("external_id", "assigning_authority", "patient_identifier", "patient_id", "status", "start_at", "last_trigger", "source_endpoint_id"):
        op.create_index(f"ix_appointment_{column}", "appointment", [column])


def downgrade() -> None:
    pass
