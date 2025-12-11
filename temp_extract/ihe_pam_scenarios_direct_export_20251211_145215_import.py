#!/usr/bin/env python3
"""
Script d'import des scénarios IHE PAM en production.
Importe les données depuis: ihe_pam_scenarios_direct_export_20251211_145215.json

INSTRUCTIONS D'UTILISATION:
1. Copiez ce script et le fichier JSON sur votre serveur de production
2. Adaptez la configuration de base de données ci-dessous selon votre environnement
3. Exécutez: python ihe_pam_scenarios_direct_export_20251211_145215_import.py

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
DATABASE_CONFIG = {
    "url": "sqlite:///medbridge_prod.db",  # Changez selon votre config de prod
    "echo": False
}

def import_scenarios_to_production():
    """Importe les scénarios dans la base de production."""

    json_file = "ihe_pam_scenarios_direct_export_20251211_145215.json"
    if not Path(json_file).exists():
        print(f"❌ Fichier d'export non trouvé: {json_file}")
        print("Vérifiez que le fichier JSON est dans le même répertoire que ce script.")
        return False

    print(f"📁 Chargement des données depuis: {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    metadata = export_data["metadata"]

    print(f"📊 Import de {len(scenarios)} scénarios IHE PAM")
    print(f"📅 Export original: {metadata['export_date']}")
    print(f"📝 Description: {metadata['description']}")

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
    #             print(f"  ⏭️  {scenario_data['name']}: déjà existant")
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
    #         print(f"  ✅ {scenario_data['name']}: importé ({len(step_data['steps'])} étapes)")
    #         imported_count += 1
    #
    #     print(f"\n📊 Résumé de l'import:")
    #     print(f"  ✅ Importés: {imported_count}")
    #     print(f"  ⏭️  Ignorés (déjà existants): {skipped_count}")

    # Version de démonstration - affiche juste les scénarios
    print("\n📋 Scénarios à importer (aperçu):")
    for i, scenario in enumerate(scenarios[:10]):  # Affiche les 10 premiers
        steps_count = len(scenario.get('steps', []))
        category = scenario.get('category', 'N/A')
        print(f"  {i+1:2d}. {scenario['name']} ({steps_count} étapes, cat: {category})")

    if len(scenarios) > 10:
        print(f"  ... et {len(scenarios) - 10} autres scénarios")

    print("\n⚠️  Import réel commenté - décommentez le code ci-dessus après adaptation")
    print("💡 Adressez-vous à votre administrateur système pour la configuration de production")

    return True

if __name__ == "__main__":
    print("🚀 Import des scénarios IHE PAM en production")
    print(f"📅 Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    success = import_scenarios_to_production()
    if success:
        print("\n✨ Aperçu terminé avec succès !")
    else:
        print("\n❌ Échec de l'aperçu")
        sys.exit(1)
