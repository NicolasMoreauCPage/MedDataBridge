#!/usr/bin/env python3
"""
Exporte les scénarios IHE PAM de la base de données locale vers des fichiers
pour déploiement en production.

Ce script :
1. Récupère tous les scénarios IHE PAM de la base locale
2. Les exporte dans des fichiers JSON structurés
3. Crée un script d'import pour la production
4. Génère une archive prête pour le déploiement
"""
import os
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Ajouter le répertoire parent au path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select

def export_scenarios_to_json() -> Dict[str, Any]:
    """Exporte tous les scénarios IHE PAM vers un dictionnaire JSON."""

    with Session(engine) as session:
        # Récupérer tous les scénarios avec "IHE PAM" dans le nom
        scenarios = session.exec(
            select(InteropScenario).where(InteropScenario.name.like("%IHE PAM%"))
        ).all()

        print(f"📊 Export de {len(scenarios)} scénarios IHE PAM")

        export_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "total_scenarios": len(scenarios),
                "source": "MedDataBridge Local Database",
                "description": "Scénarios IHE PAM importés depuis le programme Java d'intégration"
            },
            "scenarios": []
        }

        for scenario in scenarios:
            # Récupérer les étapes du scénario
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
                "source_path": scenario.source_path,
                "tags": scenario.tags,
                "is_active": scenario.is_active,
                "steps": []
            }

            for step in steps:
                step_data = {
                    "id": step.id,
                    "order_index": step.order_index,
                    "name": step.name,
                    "message_format": step.message_format,
                    "message_type": step.message_type,
                    "payload": step.payload
                }
                scenario_data["steps"].append(step_data)

            export_data["scenarios"].append(scenario_data)
            print(f"  ✅ {scenario.name} ({len(steps)} étapes)")

        return export_data

def create_import_script(export_data: Dict[str, Any], output_dir: Path) -> Path:
    """Crée un script d'import pour la production."""

    script_content = '''#!/usr/bin/env python3
"""
Script d'import des scénarios IHE PAM en production.
Généré automatiquement par export_ihe_pam_scenarios.py
"""
import sys
from pathlib import Path
from typing import Dict, List, Any

# Configuration pour la production
PRODUCTION_DB_URL = "sqlite:///medbridge_prod.db"  # À adapter selon votre configuration

def import_scenarios_to_production(scenarios_data: List[Dict[str, Any]]) -> None:
    """Importe les scénarios dans la base de production."""

    # TODO: Adapter selon votre configuration de base de données de production
    # from your_production_db import engine
    # from your_models import InteropScenario, InteropScenarioStep

    print(f"🚀 Import de {len(scenarios_data)} scénarios IHE PAM en production")

    # with Session(engine) as session:
    #     for scenario_data in scenarios_data:
    #         # Vérifier si le scénario existe déjà
    #         existing = session.exec(
    #             select(InteropScenario).where(InteropScenario.name == scenario_data["name"])
    #         ).first()
    #
    #         if existing:
    #             print(f"  ⏭️  {scenario_data['name']}: déjà existant")
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
    #         print(f"  ✅ {scenario_data['name']}: importé")

def main():
    """Point d'entrée principal."""
    # Charger les données exportées
    export_file = Path(__file__).parent / "ihe_pam_scenarios_export.json"
    if not export_file.exists():
        print(f"❌ Fichier d'export non trouvé: {export_file}")
        return

    with open(export_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)

    scenarios = export_data["scenarios"]
    print(f"📁 {len(scenarios)} scénarios à importer")

    # TODO: Décommenter et adapter quand la configuration de production est prête
    # import_scenarios_to_production(scenarios)
    print("⚠️  Import en production - À implémenter selon votre configuration DB")

if __name__ == "__main__":
    main()
'''

    script_path = output_dir / "import_ihe_pam_scenarios_production.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)

    # Rendre le script exécutable (sur Unix)
    try:
        os.chmod(script_path, 0o755)
    except:
        pass  # Ignore sur Windows

    return script_path

def create_seed_script(export_data: Dict[str, Any], output_dir: Path) -> Path:
    """Crée un script seed pour inclusion dans les données initiales."""

    scenarios = export_data["scenarios"]

    script_content = f'''#!/usr/bin/env python3
"""
Seed script pour les scénarios IHE PAM.
Généré automatiquement par export_ihe_pam_scenarios.py le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Ce script peut être intégré dans votre processus de seed initial.
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select

def seed_ihe_pam_scenarios():
    """Seed les scénarios IHE PAM dans la base de données."""

    scenarios_data = {json.dumps(scenarios, indent=2, ensure_ascii=False)}

    with Session(engine) as session:
        created_count = 0
        skipped_count = 0

        for scenario_data in scenarios_data:
            # Vérifier si le scénario existe déjà
            existing = session.exec(
                select(InteropScenario).where(InteropScenario.name == scenario_data["name"])
            ).first()

            if existing:
                print(f"  ⏭️  {{scenario_data['name']}}: déjà existant")
                skipped_count += 1
                continue

            # Créer le scénario
            scenario = InteropScenario(
                key=scenario_data["key"],
                name=scenario_data["name"],
                description=scenario_data["description"],
                category=scenario_data["category"],
                protocol=scenario_data["protocol"],
                source_path=scenario_data["source_path"],
                tags=scenario_data["tags"],
                is_active=scenario_data["is_active"]
            )
            session.add(scenario)
            session.flush()

            # Créer les étapes
            for step_data in scenario_data["steps"]:
                step = InteropScenarioStep(
                    scenario_id=scenario.id,
                    order_index=step_data["order_index"],
                    name=step_data["name"],
                    message_format=step_data["message_format"],
                    message_type=step_data["message_type"],
                    payload=step_data["payload"]
                )
                session.add(step)

            session.commit()
            print(f"  ✅ {{scenario_data['name']}}: créé")
            created_count += 1

        print(f"\\n📊 Résumé du seed:")
        print(f"  ✅ Créés: {{created_count}}")
        print(f"  ⏭️  Ignorés (déjà existants): {{skipped_count}}")

if __name__ == "__main__":
    print("🌱 Seed des scénarios IHE PAM...")
    seed_ihe_pam_scenarios()
    print("✨ Seed terminé !")
'''

    script_path = output_dir / "seed_ihe_pam_scenarios.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)

    return script_path

def create_deployment_archive(output_dir: Path) -> Path:
    """Crée une archive ZIP pour le déploiement."""

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_name = f"ihe_pam_scenarios_deployment_{timestamp}.zip"
    archive_path = output_dir / archive_name

    print(f"📦 Création de l'archive de déploiement: {archive_name}")

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Ajouter tous les fichiers du répertoire de sortie
        for file_path in output_dir.glob('*'):
            if file_path.is_file() and file_path != archive_path:
                zf.write(file_path, file_path.name)
                print(f"  📄 Ajouté: {file_path.name}")

    return archive_path

def main():
    """Fonction principale."""
    print("🚀 Export des scénarios IHE PAM pour déploiement en production")

    # Créer le répertoire de sortie
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(f"ihe_pam_export_{timestamp}")
    output_dir.mkdir(exist_ok=True)

    print(f"📁 Répertoire de sortie: {output_dir}")

    try:
        # 1. Exporter les scénarios
        print("\\n📊 Étape 1: Export depuis la base de données locale")
        export_data = export_scenarios_to_json()

        # 2. Sauvegarder en JSON
        json_file = output_dir / "ihe_pam_scenarios_export.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"  💾 Données exportées: {json_file}")

        # 3. Créer le script d'import pour la production
        print("\\n🔧 Étape 2: Création du script d'import production")
        import_script = create_import_script(export_data, output_dir)
        print(f"  📝 Script d'import créé: {import_script}")

        # 4. Créer le script seed
        print("\\n🌱 Étape 3: Création du script seed")
        seed_script = create_seed_script(export_data, output_dir)
        print(f"  🌱 Script seed créé: {seed_script}")

        # 5. Créer l'archive de déploiement
        print("\\n📦 Étape 4: Création de l'archive de déploiement")
        archive = create_deployment_archive(output_dir)
        print(f"  📦 Archive créée: {archive}")

        # 6. Créer un README
        readme_content = f'''# Déploiement des Scénarios IHE PAM

Archive générée le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Contenu

- `ihe_pam_scenarios_export.json` : Données brutes des scénarios exportés
- `import_ihe_pam_scenarios_production.py` : Script d'import pour la production
- `seed_ihe_pam_scenarios.py` : Script seed pour inclusion dans les données initiales

## Utilisation

### Option 1: Import direct en production
```bash
python import_ihe_pam_scenarios_production.py
```

### Option 2: Intégration dans le seed
Copiez le contenu de `seed_ihe_pam_scenarios.py` dans votre processus de seed initial.

## Statistiques

- **Total scénarios**: {export_data["metadata"]["total_scenarios"]}
- **Source**: {export_data["metadata"]["source"]}
- **Description**: {export_data["metadata"]["description"]}

## Catégories représentées

{chr(10).join(f"- {cat}: {count}" for cat, count in {
    "HOSPITALISATION": len([s for s in export_data["scenarios"] if s["category"] == "HOSPITALISATION"]),
    "MATERNITE": len([s for s in export_data["scenarios"] if s["category"] == "MATERNITE"]),
    "PREADMISSION": len([s for s in export_data["scenarios"] if s["category"] == "PREADMISSION"]),
    "SEANCES": len([s for s in export_data["scenarios"] if s["category"] == "SEANCES"]),
    "GENERAL": len([s for s in export_data["scenarios"] if s["category"] == "GENERAL"])
}.items())}
'''

        readme_file = output_dir / "README.md"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"  📖 README créé: {readme_file}")

        print(f"\\n✅ Export terminé avec succès!")
        print(f"📦 Archive de déploiement: {archive}")
        print(f"📁 Répertoire complet: {output_dir}")

    except Exception as e:
        print(f"❌ Erreur lors de l'export: {e}")
        return False

    return True

if __name__ == "__main__":
    main()