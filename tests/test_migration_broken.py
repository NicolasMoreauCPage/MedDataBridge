"""add_ihe_pam_scenarios_data

Revision ID: bdebea0e6af4
Revises: c8c2d706460a
Create Date: 2025-12-11 14:55:24.001359

"""
from typing import Sequence, Union
import json
import os
from datetime import datetime

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'bdebea0e6af4'
down_revision: Union[str, Sequence[str], None] = 'c8c2d706460a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Insert IHE PAM scenarios data."""

    # Get database connection
    bind = op.get_bind()

    # Current timestamp for created_at/updated_at
    now = datetime.utcnow()

    # Import models (similar to env.py)
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from app.models_scenarios import InteropScenario, InteropScenarioStep

    # Find the JSON export file
    json_file = None
    for filename in os.listdir('.'):
        if filename.startswith('ihe_pam_scenarios_direct_export_') and filename.endswith('.json'):
            json_file = filename
            break

    if not json_file:
        print("⚠️  Aucun fichier d'export JSON trouvé. Migration ignorée.")
        return

    print(f"📁 Chargement des données depuis: {json_file}")

    # Load JSON data
    with open(json_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    metadata = export_data["metadata"]

    print(f"📊 Migration: insertion de {len(scenarios)} scénarios IHE PAM")
    print(f"📅 Export original: {metadata['export_date']}")

    # Insert scenarios and steps
    interopscenario_table = sa.Table(
        'interopscenario',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String),
        sa.Column('name', sa.String),
        sa.Column('description', sa.Text),
        sa.Column('category', sa.String),
        sa.Column('protocol', sa.String),
        sa.Column('source_path', sa.Text),
        sa.Column('tags', sa.Text),
        sa.Column('is_active', sa.Boolean),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
        sa.Column('ght_context_id', sa.Integer),
        sa.Column('time_anchor_mode', sa.String),
        sa.Column('time_anchor_days_offset', sa.Integer),
        sa.Column('time_fixed_start_iso', sa.String),
        sa.Column('preserve_intervals', sa.Boolean, nullable=False),
        sa.Column('jitter_min_minutes', sa.Integer),
        sa.Column('jitter_max_minutes', sa.Integer),
        sa.Column('apply_jitter_on_events', sa.String),
    )

    interopscenariostep_table = sa.Table(
        'interopscenariostep',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('scenario_id', sa.Integer),
        sa.Column('order_index', sa.Integer),
        sa.Column('name', sa.String),
        sa.Column('message_format', sa.String),
        sa.Column('message_type', sa.String),
        sa.Column('payload', sa.Text),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )

    inserted_scenarios = 0
    inserted_steps = 0

    for scenario_data in scenarios:
        # Check if scenario already exists
        existing = bind.execute(
            sa.select(interopscenario_table.c.id).where(
                interopscenario_table.c.name == scenario_data["name"]
            )
        ).fetchone()

        if existing:
            print(f"  ⏭️  {scenario_data['name']}: déjà existant")
            continue

        # Insert scenario (compatible SQLite)
        # Insert scenario (compatible SQLite)
        bind.execute(
            sa.insert(interopscenario_table).values(
                key=scenario_data["key"],
                name=scenario_data["name"],
                description=scenario_data["description"],
                category=scenario_data["category"],
                protocol=scenario_data["protocol"],
                source_path=scenario_data["source_path"],
                tags=scenario_data["tags"],
                is_active=scenario_data["is_active"],
                created_at=now,
                updated_at=now,
                # Valeurs par défaut pour les nouvelles colonnes
                ght_context_id=None,
                time_anchor_mode=None,
                time_anchor_days_offset=None,
                time_fixed_start_iso=None,
                preserve_intervals=True,  # Valeur par défaut requise
                jitter_min_minutes=None,
                jitter_max_minutes=None,
                apply_jitter_on_events="A02,A03,A06,A07,A08",  # Valeur par défaut
            )
        )

        # Get the inserted scenario ID (compatible with SQLite)
        # For SQLite, we can use lastrowid or query by unique fields
        scenario_id_result = bind.execute(
            sa.select(interopscenario_table.c.id).where(
                interopscenario_table.c.name == scenario_data["name"]
            )
        )
        scenario_id = scenario_id_result.fetchone()[0]

        # Insert steps
        for step_data in scenario_data["steps"]:
            bind.execute(
                sa.insert(interopscenariostep_table).values(
                    scenario_id=scenario_id,
                    order_index=step_data["order_index"],
                    name=step_data["name"],
                    message_format=step_data["message_format"],
                    message_type=step_data["message_type"],
                    payload=step_data["payload"],
                    created_at=now,
                    updated_at=now,
                )
            )
            inserted_steps += 1

        inserted_scenarios += 1
        print(f"  ✅ {scenario_data['name']}: inséré ({len(scenario_data['steps'])} étapes)")

    print(f"\\n📊 Migration terminée:")
    print(f"  ✅ Scénarios insérés: {inserted_scenarios}")
    print(f"  📋 Étapes insérées: {inserted_steps}")


def downgrade() -> None:
    """Downgrade schema - Remove IHE PAM scenarios data."""

    bind = op.get_bind()

    # Tables
    interopscenario_table = sa.Table(
        'interopscenario',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String),
    )

    interopscenariostep_table = sa.Table(
        'interopscenariostep',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('scenario_id', sa.Integer),
    )

    # Delete steps first (foreign key constraint)
    deleted_steps = bind.execute(
        sa.delete(interopscenariostep_table).where(
            interopscenariostep_table.c.scenario_id.in_(
                sa.select(interopscenario_table.c.id).where(
                    interopscenario_table.c.name.like("%IHE PAM%")
                )
            )
        )
    ).rowcount

    # Delete scenarios
    deleted_scenarios = bind.execute(
        sa.delete(interopscenario_table).where(
            interopscenario_table.c.name.like("%IHE PAM%")
        )
    ).rowcount

    print(f"🗑️  Rollback migration: supprimé {deleted_scenarios} scénarios et {deleted_steps} étapes IHE PAM")
