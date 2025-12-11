#!/usr/bin/env python3
"""
Migration Alembic pour déployer les scénarios IHE PAM en production.
À exécuter avec: alembic upgrade head

Ce script doit être placé dans le répertoire alembic/versions/ de votre projet de production.
"""

import json
import os
from datetime import datetime
from alembic import op
import sqlalchemy as sa

def insert_ihe_pam_scenarios():
    """Insère les scénarios IHE PAM depuis le fichier JSON."""

    # Chemin vers le fichier JSON (à adapter selon votre déploiement)
    json_file = "ihe_pam_scenarios_direct_export_20251211_145215.json"

    if not os.path.exists(json_file):
        print(f"⚠️  Fichier {{json_file}} non trouvé. Migration ignorée.")
        print("💡 Copiez le fichier JSON dans le répertoire de l'application avant la migration.")
        return

    print(f"📁 Chargement depuis: {{json_file}}")

    with open(json_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    bind = op.get_bind()

    # Tables
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
    now = datetime.now()

    for scenario_data in scenarios:
        # Vérifier si existe déjà
        existing = bind.execute(
            sa.select(interopscenario_table.c.id).where(
                interopscenario_table.c.name == scenario_data["name"]
            )
        ).fetchone()

        if existing:
            print(f"  ⏭️  {{scenario_data['name']}}: déjà existant")
            continue

        # Insérer scénario (compatible SQLite)
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

        # Récupérer l'ID du scénario inséré (compatible SQLite)
        scenario_id_result = bind.execute(
            sa.select(interopscenario_table.c.id).where(
                interopscenario_table.c.name == scenario_data["name"]
            )
        )
        scenario_id = scenario_id_result.fetchone()[0]

        # Insérer étapes
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
        print(f"  ✅ {{scenario_data['name']}}: inséré")

    print(f"\n📊 Migration terminée: {{inserted_scenarios}} scénarios, {{inserted_steps}} étapes")

def remove_ihe_pam_scenarios():
    """Supprime les scénarios IHE PAM (rollback)."""

    bind = op.get_bind()

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

    # Supprimer étapes d'abord
    deleted_steps = bind.execute(
        sa.delete(interopscenariostep_table).where(
            interopscenariostep_table.c.scenario_id.in_(
                sa.select(interopscenario_table.c.id).where(
                    interopscenario_table.c.name.like("%IHE PAM%")
                )
            )
        )
    ).rowcount

    # Supprimer scénarios
    deleted_scenarios = bind.execute(
        sa.delete(interopscenario_table).where(
            interopscenario_table.c.name.like("%IHE PAM%")
        )
    ).rowcount

    print(f"🗑️  Rollback: supprimé {{deleted_scenarios}} scénarios et {{deleted_steps}} étapes")

# Utilisation dans une migration Alembic:
#
# def upgrade():
#     insert_ihe_pam_scenarios()
#
# def downgrade():
#     remove_ihe_pam_scenarios()
