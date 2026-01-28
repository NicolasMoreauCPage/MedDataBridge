"""
Seed all HL7/HPRIM scenarios from a JSON file into the database, using only Python (no HL7/HPRIM file dependency).
"""
import json
from pathlib import Path
from sqlmodel import Session, select
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep

# Path to the scenario seed data (can be changed if needed)
SEED_PATH = Path("data/scenarios_seed_data.json")

def seed_scenarios_from_json(seed_path=SEED_PATH):
    if not seed_path.exists():
        print(f"❌ Fichier de seed non trouvé: {seed_path}")
        return 0
    with open(seed_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    print(f"📦 Import de {len(scenarios)} scénarios depuis {seed_path}")
    imported = 0
    with Session(engine) as session:
        for scen in scenarios:
            # Check if scenario already exists by key
            existing = session.exec(select(InteropScenario).where(InteropScenario.key == scen["key"]))
            if existing.first():
                print(f"⏭️  Scénario déjà existant: {scen['name']}")
                continue
            scenario = InteropScenario(
                key=scen["key"],
                name=scen["name"],
                description=scen.get("description"),
                category=scen.get("category"),
                protocol=scen.get("protocol", "HL7"),
                source_path=scen.get("source_path"),
                tags=scen.get("tags"),
                is_active=True,
            )
            session.add(scenario)
            session.flush()  # get scenario.id
            for step in scen["steps"]:
                step_obj = InteropScenarioStep(
                    scenario_id=scenario.id,
                    order_index=step["order_index"],
                    name=step.get("name"),
                    description=step.get("description"),
                    message_format=step.get("message_format", "hl7"),
                    message_type=step.get("message_type"),
                    payload=step["payload"],
                )
                session.add(step_obj)
            session.commit()
            print(f"✅  Scénario importé: {scen['name']} ({len(scen['steps'])} étapes)")
            imported += 1
    print(f"🎉 {imported} scénarios importés.")
    return imported

if __name__ == "__main__":
    seed_scenarios_from_json()
