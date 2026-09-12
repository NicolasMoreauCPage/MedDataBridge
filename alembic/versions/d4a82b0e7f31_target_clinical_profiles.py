"""Add clinical scenario profiles per target system.

Revision ID: d4a82b0e7f31
Revises: c3f91a0d6e25
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa


revision = "d4a82b0e7f31"
down_revision = "c3f91a0d6e25"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {item["name"] for item in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "scenariotargetprofile" not in tables:
        op.create_table(
            "scenariotargetprofile",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("target_system_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("entite_juridique_id", sa.Integer(), sa.ForeignKey("entitejuridique.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("target_system_key", name="uq_scenariotargetprofile_target_system_key"),
        )
        for col in ("target_system_key", "entite_juridique_id", "is_active"):
            op.create_index(f"ix_scenariotargetprofile_{col}", "scenariotargetprofile", [col])
    if "scenariotargetlocation" not in tables:
        op.create_table(
            "scenariotargetlocation",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("scenariotargetprofile.id"), nullable=False),
            sa.Column("role", sa.String(length=48), nullable=False),
            sa.Column("unite_fonctionnelle_id", sa.Integer(), sa.ForeignKey("unitefonctionnelle.id"), nullable=True),
            sa.Column("medecin_responsable_id", sa.Integer(), sa.ForeignKey("medecinresponsable.id"), nullable=True),
            sa.Column("room", sa.String(length=20), nullable=True),
            sa.Column("bed", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("profile_id", "role", name="uq_scenario_target_location_role"),
        )
        for col in ("profile_id", "role", "unite_fonctionnelle_id", "medecin_responsable_id"):
            op.create_index(f"ix_scenariotargetlocation_{col}", "scenariotargetlocation", [col])
    cols = _columns(bind, "scenariodelivery")
    if "compiled_payload" not in cols:
        op.add_column("scenariodelivery", sa.Column("compiled_payload", sa.Text(), nullable=True))
    if "target_context_json" not in cols:
        op.add_column("scenariodelivery", sa.Column("target_context_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # Les preuves de livraison doivent rester disponibles.
    pass
