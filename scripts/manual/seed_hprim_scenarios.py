"""
Seed HPRIM scenarios directly into the database (no file dependency).
"""
from sqlmodel import Session
from sqlmodel import select
from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep

def seed_hprim_scenarios():
    from data.scenarios_hprim_seed import scenarios
    with Session(engine) as session:
        for scen in scenarios:
            existing = session.exec(
                select(InteropScenario).where(InteropScenario.key == scen["key"])
            ).first()
            if existing:
                print(f"⏭️  Scénario déjà existant: {scen['name']}")
                continue
            scenario = InteropScenario(
                key=scen["key"],
                name=scen["name"],
                description=scen.get("description"),
                category=scen.get("category"),
                protocol=scen.get("protocol", "HL7"),
                tags=scen.get("tags"),
                is_active=True,
            )
            session.add(scenario)
            session.flush()
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

if __name__ == "__main__":
    seed_hprim_scenarios()
