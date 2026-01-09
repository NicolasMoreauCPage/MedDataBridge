"""Add chambre/lit fields to scenario_ej_config for IHE PAM France conformity.

Revision ID: 0007_add_location_fields_ej_config
Revises: merge_heads_20251205
Create Date: 2025-12-05 14:00:00

IHE PAM France requires:
- PV1-3 format: PointOfCare^Room^Bed^Facility^LocationStatus
- Chambre and lit fields allow full conformity
- Medecin traitant (PV1-8) separate from attending doctor (PV1-7)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_add_location_fields_ej_config'
down_revision: Union[str, None] = 'merge_heads_20251205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ADD COLUMN with constraints, so we use batch mode
    with op.batch_alter_table('scenario_ej_config', schema=None) as batch_op:
        # Chambre/Lit Hospitalisation
        batch_op.add_column(sa.Column('chambre_hospitalisation', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('lit_hospitalisation', sa.String(20), nullable=True))
        
        # Chambre Consultation (pas de lit)
        batch_op.add_column(sa.Column('chambre_consultation', sa.String(20), nullable=True))
        
        # Chambre/Lit Urgences
        batch_op.add_column(sa.Column('chambre_urgences', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('lit_urgences', sa.String(20), nullable=True))
        
        # Chambre/Lit Mutation
        batch_op.add_column(sa.Column('chambre_mutation', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('lit_mutation', sa.String(20), nullable=True))
        
        # Médecin traitant (PV1-8)
        batch_op.add_column(sa.Column('medecin_traitant_rpps', sa.String(11), nullable=True))
        batch_op.add_column(sa.Column('medecin_traitant_nom', sa.String(100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('scenario_ej_config', schema=None) as batch_op:
        batch_op.drop_column('chambre_hospitalisation')
        batch_op.drop_column('lit_hospitalisation')
        batch_op.drop_column('chambre_consultation')
        batch_op.drop_column('chambre_urgences')
        batch_op.drop_column('lit_urgences')
        batch_op.drop_column('chambre_mutation')
        batch_op.drop_column('lit_mutation')
        batch_op.drop_column('medecin_traitant_rpps')
        batch_op.drop_column('medecin_traitant_nom')
