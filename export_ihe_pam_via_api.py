#!/usr/bin/env python3
"""
Export des scénarios IHE PAM via l'API REST pour éviter les problèmes d'import direct.
"""
import requests
import json
from datetime import datetime
import time

def wait_for_server(base_url="http://localhost:8000", timeout=30):
    """Attend que le serveur soit disponible."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/docs", timeout=5)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def export_scenarios_via_api(base_url="http://localhost:8000"):
    """Exporte les scénarios via l'API REST."""
    print("🚀 Export des scénarios IHE PAM via API REST")

    if not wait_for_server(base_url):
        print("❌ Serveur non disponible")
        return False

    try:
        # Récupérer tous les scénarios
        response = requests.get(f"{base_url}/api/scenarios", timeout=10)
        if response.status_code != 200:
            print(f"❌ Erreur API: {response.status_code}")
            return False

        all_scenarios = response.json()
        print(f"📊 {len(all_scenarios)} scénarios totaux récupérés")

        # Filtrer les scénarios IHE PAM
        ihe_pam_scenarios = [s for s in all_scenarios if 'IHE PAM' in s.get('name', '')]
        print(f"🎯 {len(ihe_pam_scenarios)} scénarios IHE PAM trouvés")

        # Récupérer les détails complets pour chaque scénario
        detailed_scenarios = []
        for scenario in ihe_pam_scenarios:
            scenario_id = scenario['id']
            print(f"  📋 Récupération détails: {scenario['name']}")

            # Récupérer les étapes du scénario
            steps_response = requests.get(f"{base_url}/api/scenarios/{scenario_id}/steps", timeout=10)
            if steps_response.status_code == 200:
                steps = steps_response.json()
                scenario['steps'] = steps
                detailed_scenarios.append(scenario)
            else:
                print(f"    ⚠️  Impossible de récupérer les étapes pour {scenario['name']}")

        # Créer les données d'export
        export_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "total_scenarios": len(detailed_scenarios),
                "source": "MedDataBridge API REST",
                "description": "Scénarios IHE PAM exportés via API pour déploiement en production"
            },
            "scenarios": detailed_scenarios
        }

        # Sauvegarder en JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ihe_pam_scenarios_api_export_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Export terminé: {filename}")
        print(f"📊 {len(detailed_scenarios)} scénarios exportés avec leurs étapes")

        # Créer un résumé
        categories = {}
        for scenario in detailed_scenarios:
            cat = scenario.get('category', 'UNKNOWN')
            categories[cat] = categories.get(cat, 0) + 1

        print("\n📂 Répartition par catégorie:")
        for cat, count in sorted(categories.items()):
            print(f"  - {cat}: {count}")

        return filename

    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        return False

def create_import_script_from_api_export(json_filename):
    """Crée un script d'import basé sur l'export API."""
    import_script = f'''#!/usr/bin/env python3
"""
Script d'import des scénarios IHE PAM en production.
Basé sur l'export API: {json_filename}

INSTRUCTIONS:
1. Copiez ce script et le fichier JSON sur votre serveur de production
2. Adaptez la configuration de base de données ci-dessous
3. Exécutez le script
"""
import json
import sys
from pathlib import Path

# Configuration de production - À ADAPTER !
PRODUCTION_DB_CONFIG = {{
    "url": "sqlite:///medbridge_prod.db",  # Changez selon votre config
    "echo": False
}}

def import_scenarios_to_production():
    """Importe les scénarios dans la base de production."""

    # Charger les données exportées
    if not Path("{json_filename}").exists():
        print(f"❌ Fichier d'export non trouvé: {json_filename}")
        return False

    with open("{json_filename}", 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    print(f"📁 {{len(scenarios)}} scénarios à importer")

    # TODO: Implémenter selon votre configuration de production
    # Exemple avec SQLAlchemy/SQLModel:
    #
    # from sqlalchemy import create_engine
    # from sqlmodel import Session
    # from your_models import InteropScenario, InteropScenarioStep
    #
    # engine = create_engine(PRODUCTION_DB_CONFIG["url"], echo=PRODUCTION_DB_CONFIG["echo"])
    #
    # with Session(engine) as session:
    #     for scenario_data in scenarios:
    #         # Vérifier si existe déjà
    #         # Créer le scénario
    #         # Créer les étapes
    #         # Commit

    print("⚠️  Import à implémenter selon votre configuration de production")
    print("\\n📋 Scénarios à importer:")
    for scenario in scenarios[:5]:  # Afficher les 5 premiers
        steps_count = len(scenario.get('steps', []))
        print(f"  - {{scenario['name']}} ({{steps_count}} étapes)")
    if len(scenarios) > 5:
        print(f"  ... et {{len(scenarios) - 5}} autres")

    return True

if __name__ == "__main__":
    print("🚀 Import des scénarios IHE PAM en production")
    success = import_scenarios_to_production()
    if success:
        print("✨ Import terminé !")
    else:
        print("❌ Échec de l'import")
'''

    script_filename = json_filename.replace('.json', '_import.py')
    with open(script_filename, 'w', encoding='utf-8') as f:
        f.write(import_script)

    print(f"📝 Script d'import créé: {script_filename}")
    return script_filename

def main():
    """Fonction principale."""
    # Démarrer le serveur si nécessaire
    print("🔍 Vérification du serveur FastAPI...")
    if not wait_for_server():
        print("⚠️  Serveur non détecté. Tentative de démarrage...")
        # Note: Le serveur devrait déjà être démarré par l'utilisateur
        print("💡 Lancez d'abord: python -m uvicorn app.app:app --reload")
        return False

    # Exporter via API
    json_file = export_scenarios_via_api()
    if not json_file:
        return False

    # Créer le script d'import
    import_script = create_import_script_from_api_export(json_file)

    print(f"\\n✅ Export complet terminé!")
    print(f"📄 Fichier JSON: {json_file}")
    print(f"📝 Script d'import: {import_script}")
    print("\\n🚀 Pour déployer en production:")
    print("1. Copiez ces deux fichiers sur votre serveur")
    print("2. Adaptez la configuration DB dans le script d'import")
    print("3. Exécutez le script d'import")

    return True

if __name__ == "__main__":
    main()