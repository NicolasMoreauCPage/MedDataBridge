#!/usr/bin/env python3
"""
Export simplifié des scénarios IHE PAM vers JSON pour déploiement.
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

def main():
    print("🚀 Export simplifié des scénarios IHE PAM")

    try:
        with Session(engine) as session:
            # Récupérer tous les scénarios IHE PAM
            scenarios = session.exec(
                select(InteropScenario).where(InteropScenario.name.like("%IHE PAM%"))
            ).all()

            print(f"📊 {len(scenarios)} scénarios trouvés")

            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "total_scenarios": len(scenarios),
                    "description": "Scénarios IHE PAM pour déploiement en production"
                },
                "scenarios": []
            }

            for i, scenario in enumerate(scenarios):
                print(f"  📋 Export {i+1}/{len(scenarios)}: {scenario.name}")

                # Récupérer les étapes
                steps = session.exec(
                    select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == scenario.id)
                    .order_by(InteropScenarioStep.order_index)
                ).all()

                scenario_data = {
                    "id": scenario.id,
                    "key": scenario.key,
                    "name": scenario.name,
                    "description": scenario.description,
                    "category": scenario.category,
                    "protocol": scenario.protocol,
                    "tags": scenario.tags,
                    "is_active": scenario.is_active,
                    "steps": [
                        {
                            "order_index": step.order_index,
                            "name": step.name,
                            "message_type": step.message_type,
                            "payload": step.payload
                        } for step in steps
                    ]
                }

                export_data["scenarios"].append(scenario_data)

            # Sauvegarder en JSON
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ihe_pam_scenarios_export_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Export terminé: {filename}")
            print(f"📊 {len(scenarios)} scénarios exportés")

            # Créer un script d'import simple
            import_script = f'''#!/usr/bin/env python3
"""
Script d'import des scénarios IHE PAM en production.
Utilise le fichier: {filename}
"""
import json
import sys
from pathlib import Path

# TODO: Adapter selon votre configuration de production
def import_scenarios():
    with open("{filename}", 'r', encoding='utf-8') as f:
        data = json.load(f)

    scenarios = data["scenarios"]
    print(f"📁 {{len(scenarios)}} scénarios à importer")

    # TODO: Implémenter l'import selon votre configuration DB de production
    for scenario in scenarios:
        print(f"  - {{scenario['name']}} ({{len(scenario['steps'])}} étapes)")

    print("⚠️  Import à implémenter selon votre configuration de production")

if __name__ == "__main__":
    import_scenarios()
'''

            script_filename = f"import_ihe_pam_production_{timestamp}.py"
            with open(script_filename, 'w', encoding='utf-8') as f:
                f.write(import_script)

            print(f"📝 Script d'import créé: {script_filename}")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

    return True

if __name__ == "__main__":
    main()