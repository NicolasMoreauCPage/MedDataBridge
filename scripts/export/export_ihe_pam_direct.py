#!/usr/bin/env python3
"""
Export simple et direct des scénarios IHE PAM depuis la base de données.
"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select

def export_ihe_pam_scenarios_direct():
    """Export direct depuis la base de données."""

    print("🚀 Export direct des scénarios IHE PAM depuis la base de données")

    try:
        with Session(engine) as session:
            # Récupérer tous les scénarios IHE PAM
            scenarios = session.exec(
                select(InteropScenario).where(InteropScenario.name.like("%IHE PAM%"))
            ).all()

            print(f"📊 {len(scenarios)} scénarios IHE PAM trouvés")

            if not scenarios:
                print("❌ Aucun scénario IHE PAM trouvé")
                return None

            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "total_scenarios": len(scenarios),
                    "description": "Scénarios IHE PAM exportés directement depuis MedDataBridge",
                    "source": "MedDataBridge Local Database Direct Export"
                },
                "scenarios": []
            }

            for i, scenario in enumerate(scenarios):
                print(f"  📋 Export {i+1}/{len(scenarios)}: {scenario.name}")

                # Récupérer les étapes
                steps = session.exec(
                    select(InteropScenarioStep)
                    .where(InteropScenarioStep.scenario_id == scenario.id)
                    .order_by(InteropScenarioStep.order_index)
                ).all()

                scenario_data = {
                    "id": scenario.id,
                    "key": scenario.key,
                    "name": scenario.name,
                    "description": scenario.description or "",
                    "category": scenario.category or "",
                    "protocol": scenario.protocol or "",
                    "source_path": scenario.source_path or "",
                    "tags": scenario.tags or "",
                    "is_active": scenario.is_active,
                    "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
                    "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else None,
                    "steps": []
                }

                for step in steps:
                    step_data = {
                        "id": step.id,
                        "order_index": step.order_index,
                        "name": step.name or "",
                        "message_format": step.message_format or "",
                        "message_type": step.message_type or "",
                        "payload": step.payload or "",
                        "created_at": step.created_at.isoformat() if step.created_at else None,
                        "updated_at": step.updated_at.isoformat() if step.updated_at else None
                    }
                    scenario_data["steps"].append(step_data)

                export_data["scenarios"].append(scenario_data)

            # Sauvegarder en JSON
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ihe_pam_scenarios_direct_export_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Export terminé: {filename}")
            print(f"📊 {len(scenarios)} scénarios exportés avec leurs étapes")

            # Statistiques
            categories = {}
            total_steps = 0
            for scenario in export_data["scenarios"]:
                cat = scenario.get('category', 'UNKNOWN')
                categories[cat] = categories.get(cat, 0) + 1
                total_steps += len(scenario.get('steps', []))

            print(f"\\n📈 Statistiques:")
            print(f"  📊 Scénarios: {len(scenarios)}")
            print(f"  📋 Étapes totales: {total_steps}")
            print(f"  📂 Catégories: {len(categories)}")

            print("\\n📂 Répartition par catégorie:")
            for cat, count in sorted(categories.items()):
                print(f"  - {cat}: {count}")

            return filename

    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_production_import_script(json_filename):
    """Crée un script d'import pour la production basé sur l'export."""

    script_content = f'''#!/usr/bin/env python3
"""
Script d'import des scénarios IHE PAM en production.
Importe les données depuis: {json_filename}

INSTRUCTIONS D'UTILISATION:
1. Copiez ce script et le fichier JSON sur votre serveur de production
2. Adaptez la configuration de base de données ci-dessous selon votre environnement
3. Exécutez: python {json_filename.replace('.json', '_import.py')}

CONFIGURATION PRODUCTION:
- Modifiez DATABASE_URL selon votre configuration
- Assurez-vous que les modèles SQLModel sont disponibles
- Vérifiez que la base de données de production est accessible
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Configuration de production - À ADAPTER !
DATABASE_CONFIG = {{
    "url": "sqlite:///medbridge_prod.db",  # Changez selon votre config de prod
    "echo": False
}}

def import_scenarios_to_production():
    """Importe les scénarios dans la base de production."""

    json_file = "{json_filename}"
    if not Path(json_file).exists():
        print(f"❌ Fichier d'export non trouvé: {{json_file}}")
        print("Vérifiez que le fichier JSON est dans le même répertoire que ce script.")
        return False

    print(f"📁 Chargement des données depuis: {{json_file}}")

    with open(json_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    metadata = export_data["metadata"]

    print(f"📊 Import de {{len(scenarios)}} scénarios IHE PAM")
    print(f"📅 Export original: {{metadata['export_date']}}")
    print(f"📝 Description: {{metadata['description']}}")

    # TODO: Décommenter et adapter quand la configuration de production est prête
    #
    # from sqlalchemy import create_engine
    # from sqlmodel import Session
    # from your_models import InteropScenario, InteropScenarioStep  # Adaptez les imports
    #
    # engine = create_engine(DATABASE_CONFIG["url"], echo=DATABASE_CONFIG["echo"])
    #
    # with Session(engine) as session:
    #     imported_count = 0
    #     skipped_count = 0
    #
    #     for scenario_data in scenarios:
    #         # Vérifier si le scénario existe déjà
    #         existing = session.exec(
    #             select(InteropScenario).where(InteropScenario.name == scenario_data["name"])
    #         ).first()
    #
    #         if existing:
    #             print(f"  ⏭️  {{scenario_data['name']}}: déjà existant")
    #             skipped_count += 1
    #             continue
    #
    #         # Créer le scénario
    #         scenario = InteropScenario(
    #             key=scenario_data["key"],
    #             name=scenario_data["name"],
    #             description=scenario_data["description"],
    #             category=scenario_data["category"],
    #             protocol=scenario_data["protocol"],
    #             source_path=scenario_data["source_path"],
    #             tags=scenario_data["tags"],
    #             is_active=scenario_data["is_active"]
    #         )
    #         session.add(scenario)
    #         session.flush()
    #
    #         # Créer les étapes
    #         for step_data in scenario_data["steps"]:
    #             step = InteropScenarioStep(
    #                 scenario_id=scenario.id,
    #                 order_index=step_data["order_index"],
    #                 name=step_data["name"],
    #                 message_format=step_data["message_format"],
    #                 message_type=step_data["message_type"],
    #                 payload=step_data["payload"]
    #             )
    #             session.add(step)
    #
    #         session.commit()
    #         print(f"  ✅ {{scenario_data['name']}}: importé ({{len(step_data['steps'])}} étapes)")
    #         imported_count += 1
    #
    #     print(f"\\n📊 Résumé de l'import:")
    #     print(f"  ✅ Importés: {{imported_count}}")
    #     print(f"  ⏭️  Ignorés (déjà existants): {{skipped_count}}")

    # Version de démonstration - affiche juste les scénarios
    print("\\n📋 Scénarios à importer (aperçu):")
    for i, scenario in enumerate(scenarios[:10]):  # Affiche les 10 premiers
        steps_count = len(scenario.get('steps', []))
        category = scenario.get('category', 'N/A')
        print(f"  {{i+1:2d}}. {{scenario['name']}} ({{steps_count}} étapes, cat: {{category}})")

    if len(scenarios) > 10:
        print(f"  ... et {{len(scenarios) - 10}} autres scénarios")

    print("\\n⚠️  Import réel commenté - décommentez le code ci-dessus après adaptation")
    print("💡 Adressez-vous à votre administrateur système pour la configuration de production")

    return True

if __name__ == "__main__":
    print("🚀 Import des scénarios IHE PAM en production")
    print(f"📅 Généré le: {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}")

    success = import_scenarios_to_production()
    if success:
        print("\\n✨ Aperçu terminé avec succès !")
    else:
        print("\\n❌ Échec de l'aperçu")
        sys.exit(1)
'''

    script_filename = json_filename.replace('.json', '_import.py')
    with open(script_filename, 'w', encoding='utf-8') as f:
        f.write(script_content)

    print(f"📝 Script d'import créé: {script_filename}")
    return script_filename

def main():
    """Fonction principale."""

    # Export direct depuis la base
    json_file = export_ihe_pam_scenarios_direct()
    if not json_file:
        print("❌ Échec de l'export")
        return False

    # Créer le script d'import
    import_script = create_production_import_script(json_file)

    print(f"\\n✅ Export complet terminé!")
    print(f"📄 Fichier JSON: {json_file}")
    print(f"📝 Script d'import: {import_script}")

    print("\\n🚀 Pour déployer en production:")
    print("1. Copiez ces deux fichiers sur votre serveur de production")
    print("2. Adaptez la configuration DB dans le script d'import")
    print("3. Exécutez le script d'import")

    print("\\n📦 Fichiers générés:")
    print(f"  - {json_file} (données des scénarios)")
    print(f"  - {import_script} (script d'import pour la production)")

    return True

if __name__ == "__main__":
    main()