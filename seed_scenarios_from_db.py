"""
Seed script pour les scénarios d'intégration HL7/HPRIM
Ce script insère directement les données depuis la base de données actuelle
au lieu de relire les fichiers source.
"""

import json
import os
from pathlib import Path
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from datetime import datetime


def load_seed_data():
    """Charge les données de seed depuis le fichier JSON"""
    seed_file = Path(__file__).parent / "scenarios_seed_data.json"
    with open(seed_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_scenarios_from_db():
    """Importe les scénarios depuis les données de seed"""

    print("🌱 Chargement des données de seed...")

    try:
        seed_data = load_seed_data()
        print(f"📊 {len(seed_data)} scénarios trouvés dans le seed")

    except FileNotFoundError:
        print("❌ Fichier scenarios_seed_data.json non trouvé")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Erreur de parsing JSON: {e}")
        return

    with Session(engine) as session:
        imported_count = 0
        skipped_count = 0

        for scenario_data in seed_data:
            try:
                scenario_key = scenario_data['key']

                # Vérifier si le scénario existe déjà
                existing = session.exec(
                    select(InteropScenario).where(InteropScenario.key == scenario_key)
                ).first()

                if existing:
                    print(f"  ⏭️ {scenario_data['name']}: déjà existant")
                    skipped_count += 1
                    continue

                # Créer le scénario
                scenario = InteropScenario(
                    key=scenario_key,
                    name=scenario_data['name'],
                    description=scenario_data['description'],
                    category=scenario_data['category'],
                    protocol=scenario_data['protocol'],
                    source_path=scenario_data['source_path'],
                    tags=scenario_data['tags']
                )

                session.add(scenario)
                session.flush()  # Pour obtenir l'ID

                # Créer les étapes
                for step_data in scenario_data['steps']:
                    step = InteropScenarioStep(
                        scenario_id=scenario.id,
                        order_index=step_data['order_index'],
                        name=step_data['name'],
                        description=step_data['description'],
                        message_format=step_data['message_format'],
                        message_type=step_data['message_type'],
                        payload=step_data['payload']
                    )
                    session.add(step)

                session.commit()
                imported_count += 1

                steps_count = len(scenario_data['steps'])
                print(f"  ✅ {scenario_data['name']}: {steps_count} étapes")

            except Exception as e:
                print(f"  ❌ Erreur avec {scenario_data.get('name', 'scénario inconnu')}: {e}")
                session.rollback()
                continue

        print("\n🎉 Seed terminé !")
        print(f"   • {imported_count} scénarios créés")
        print(f"   • {skipped_count} scénarios ignorés (déjà existants)")
        print(f"   • Total: {imported_count + skipped_count} scénarios traités")


def verify_seed_integrity():
    """Vérifie l'intégrité du seed par rapport aux données exportées"""

    print("\n🔍 Vérification de l'intégrité du seed...")

    try:
        seed_data = load_seed_data()
    except Exception as e:
        print(f"❌ Impossible de charger les données de seed: {e}")
        return

    with Session(engine) as session:
        # Compter les scénarios par catégorie
        total_scenarios = session.exec(select(InteropScenario)).all()
        hl7_scenarios = [s for s in total_scenarios if s.category == 'IHE_PAM']
        hprim_scenarios = [s for s in total_scenarios if s.category == 'HPRIM_COTATION']

        seed_hl7 = [s for s in seed_data if s['category'] == 'IHE_PAM']
        seed_hprim = [s for s in seed_data if s['category'] == 'HPRIM_COTATION']

        print("📊 Comparaison Seed vs Base de données:")
        print(f"   • HL7 IHE PAM: {len(seed_hl7)} (seed) vs {len(hl7_scenarios)} (BDD)")
        print(f"   • HPRIM XML: {len(seed_hprim)} (seed) vs {len(hprim_scenarios)} (BDD)")

        # Vérifier quelques exemples
        if hl7_scenarios:
            print(f"   • Exemple HL7: {hl7_scenarios[0].name}")
        if hprim_scenarios:
            print(f"   • Exemple HPRIM: {hprim_scenarios[0].name}")

        # Calculer le nombre total d'étapes
        total_steps_seed = sum(len(s['steps']) for s in seed_data)
        total_steps_db = session.exec(select(InteropScenarioStep)).all()

        print(f"   • Étapes totales: {total_steps_seed} (seed) vs {len(total_steps_db)} (BDD)")

        if len(total_scenarios) == len(seed_data) and len(total_steps_db) == total_steps_seed:
            print("✅ Intégrité du seed validée !")
        else:
            print("⚠️ Différences détectées entre seed et base de données")


if __name__ == "__main__":
    print("🚀 Script de seed des scénarios d'intégration")
    print("=" * 50)

    # Importer les scénarios
    seed_scenarios_from_db()

    # Vérifier l'intégrité
    verify_seed_integrity()

    print("\n✨ Seed complet ! Vous pouvez utiliser ce script pour initialiser")
    print("   une nouvelle base de données avec tous les scénarios de test.")