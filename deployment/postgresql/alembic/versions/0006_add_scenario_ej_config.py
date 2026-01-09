"""add scenario_ej_config table

Revision ID: 0006_add_scenario_ej_config
Revises: 0005_add_scenario_execution_runs
Create Date: 2025-12-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_add_scenario_ej_config"
down_revision = "0005_add_scenario_execution_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "scenario_ej_config" not in existing:
        op.create_table(
            "scenario_ej_config",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entite_juridique_id", sa.Integer(), sa.ForeignKey("entitejuridique.id"), nullable=False, unique=True, index=True),
            
            # UF Hospitalisation
            sa.Column("uf_hospitalisation_id", sa.Integer(), sa.ForeignKey("unitefonctionnelle.id"), nullable=True),
            sa.Column("medecin_hospitalisation_rpps", sa.String(11), nullable=True),
            sa.Column("medecin_hospitalisation_nom", sa.String(100), nullable=True),
            
            # UF Consultation externe
            sa.Column("uf_consultation_id", sa.Integer(), sa.ForeignKey("unitefonctionnelle.id"), nullable=True),
            sa.Column("medecin_consultation_rpps", sa.String(11), nullable=True),
            sa.Column("medecin_consultation_nom", sa.String(100), nullable=True),
            
            # UF Urgences
            sa.Column("uf_urgences_id", sa.Integer(), sa.ForeignKey("unitefonctionnelle.id"), nullable=True),
            sa.Column("medecin_urgences_rpps", sa.String(11), nullable=True),
            sa.Column("medecin_urgences_nom", sa.String(100), nullable=True),
            
            # UF Mutation cible
            sa.Column("uf_mutation_cible_id", sa.Integer(), sa.ForeignKey("unitefonctionnelle.id"), nullable=True),
            sa.Column("medecin_mutation_rpps", sa.String(11), nullable=True),
            sa.Column("medecin_mutation_nom", sa.String(100), nullable=True),
            
            # Métadonnées
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("scenario_ej_config")
