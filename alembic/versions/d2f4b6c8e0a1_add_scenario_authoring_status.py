"""Add authoring lifecycle metadata to interoperability scenarios.

Revision ID: d2f4b6c8e0a1
Revises: c7e1f2a4b603
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "d2f4b6c8e0a1"
down_revision = "c7e1f2a4b603"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("interopscenario")}
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("interopscenario")}
    if "authoring_status" not in columns:
        op.add_column(
            "interopscenario",
            sa.Column("authoring_status", sa.String(), nullable=False, server_default="ready"),
        )
    if "ix_interopscenario_authoring_status" not in indexes:
        op.create_index("ix_interopscenario_authoring_status", "interopscenario", ["authoring_status"])
    if "authoring_metadata_json" not in columns:
        op.add_column("interopscenario", sa.Column("authoring_metadata_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # Les brouillons existants doivent être conservés si une installation revient
    # temporairement à une version antérieure du logiciel.
    pass
