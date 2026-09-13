"""Store cotation billing status as a boolean.

Revision ID: c7e1f2a4b603
Revises: b6d4e2f7a901
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa


revision = "c7e1f2a4b603"
down_revision = "b6d4e2f7a901"
branch_labels = None
depends_on = None


ACT_TABLES = ("ccamact", "ngapact", "ucdact", "lppact")


def upgrade() -> None:
    """Convert legacy HPRIM text values to a local boolean representation."""

    bind = op.get_bind()
    for table in ACT_TABLES:
        # Works on both SQLite and PostgreSQL before the column type changes.
        bind.execute(
            sa.text(
                f"UPDATE {table} "
                "SET facture = CASE "
                "WHEN lower(trim(CAST(facture AS TEXT))) IN "
                "('oui', 'true', 't', '1', 'yes', 'y') THEN 1 "
                "ELSE 0 END"
            )
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "facture",
                existing_type=sa.String(),
                type_=sa.Boolean(),
                existing_nullable=False,
                server_default=sa.false(),
                postgresql_using="facture::boolean",
            )


def downgrade() -> None:
    """Restore the historical textual representation for older deployments."""

    bind = op.get_bind()
    for table in ACT_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "facture",
                existing_type=sa.Boolean(),
                type_=sa.String(),
                existing_nullable=False,
                server_default="non",
                postgresql_using="facture::text",
            )
        bind.execute(
            sa.text(
                f"UPDATE {table} "
                "SET facture = CASE WHEN facture THEN 'oui' ELSE 'non' END"
            )
        )
