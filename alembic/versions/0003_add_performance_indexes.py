"""Add performance indexes for dashboards and lists.

This migration adds indexes to optimize dashboard queries and list performance:
- MessageLog: composite index (status, endpoint_id, created_at DESC)
- Mouvement: indexes for when DESC and (venue_id, when DESC) 
- Venue: index on dossier_id

Expected performance improvement: dashboard loads from 2-3s to <300ms.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_performance_indexes"
down_revision = "0002_add_strict_pam_fr_entitejuridique"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # MessageLog: composite index for dashboard filtering by status/endpoint + sorting by date
    op.create_index(
        "idx_messagelog_status_endpoint_created",
        "messagelog",
        ["status", "endpoint_id", "created_at"],
        unique=False
    )
    
    # Mouvement: index for temporal sorting (list views)
    op.create_index(
        "idx_mouvement_when",
        "mouvement",
        ["when"],
        unique=False
    )
    
    # Mouvement: composite index for venue-scoped temporal queries
    op.create_index(
        "idx_mouvement_venue_when",
        "mouvement",
        ["venue_id", "when"],
        unique=False
    )
    
    # Venue: index for dossier relationships (foreign key optimization)
    op.create_index(
        "idx_venue_dossier",
        "venue",
        ["dossier_id"],
        unique=False
    )


def downgrade() -> None:
    # Drop indexes in reverse order
    op.drop_index("idx_venue_dossier", table_name="venue")
    op.drop_index("idx_mouvement_venue_when", table_name="mouvement")
    op.drop_index("idx_mouvement_when", table_name="mouvement")
    op.drop_index("idx_messagelog_status_endpoint_created", table_name="messagelog")
