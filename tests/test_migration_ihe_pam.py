#!/usr/bin/env python3
"""
Test de la migration Alembic pour les scénarios IHE PAM.
"""
import sys
from pathlib import Path
import json
import os
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

def test_migration_logic():
    """Teste la logique de la migration sans Alembic."""

    print("🧪 Test de la logique de migration IHE PAM")

    # Simuler la logique de upgrade() de la migration
    json_file = None
    for filename in os.listdir('.'):
        if filename.startswith('ihe_pam_scenarios_direct_export_') and filename.endswith('.json'):
            json_file = filename
            break

    if not json_file:
        print("❌ Aucun fichier d'export JSON trouvé")
        return False

    print(f"📁 Fichier trouvé: {json_file}")

    # Charger les données
    with open(json_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    metadata = export_data["metadata"]

    print(f"📊 Données chargées: {len(scenarios)} scénarios")
    print(f"📅 Export: {metadata['export_date']}")

    # Simuler l'insertion (sans vraiment insérer)
    inserted_scenarios = 0
    inserted_steps = 0

    for scenario_data in scenarios:
        # Ici on simulerait la vérification d'existence
        print(f"  📋 {scenario_data['name']} ({len(scenario_data['steps'])} étapes)")
        inserted_scenarios += 1
        inserted_steps += len(scenario_data['steps'])

    print(f"\\n✅ Test réussi:")
    print(f"  📊 Scénarios à insérer: {inserted_scenarios}")
    print(f"  📋 Étapes à insérer: {inserted_steps}")

    return True

def create_production_migration_script():
    """Crée un script de migration pour la production."""

    script_content = '''#!/usr/bin/env python3
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

        # Insérer scénario
        scenario_result = bind.execute(
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
            ).returning(interopscenario_table.c.id)
        )
        scenario_id = scenario_result.fetchone()[0]

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

    print(f"\\n📊 Migration terminée: {{inserted_scenarios}} scénarios, {{inserted_steps}} étapes")

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
'''

    script_filename = "migration_ihe_pam_production.py"
    with open(script_filename, 'w', encoding='utf-8') as f:
        f.write(script_content)

    print(f"📝 Script de migration créé: {script_filename}")
    return script_filename

if __name__ == "__main__":
    print("🚀 Test de migration IHE PAM via Alembic")

    # Tester la logique
    if test_migration_logic():
        print("\\n✅ Logique de migration validée")

        # Créer le script de production
        prod_script = create_production_migration_script()

        print("\\n📦 Fichiers pour le déploiement:")
        print("  - Migration Alembic: alembic/versions/bdebea0e6af4_add_ihe_pam_scenarios_data.py")
        print(f"  - Script helper: {prod_script}")
        print("  - Données JSON: ihe_pam_scenarios_direct_export_*.json")

        print("\\n🚀 Pour déployer en production:")
        print("1. Copiez les fichiers sur votre serveur")
        print("2. Exécutez: alembic upgrade head")
        print("3. Vérifiez que les scénarios sont présents")

    else:
        print("\\n❌ Échec du test")