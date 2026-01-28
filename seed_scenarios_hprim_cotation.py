"""
Seed all scenarios for a specific category from a JSON file into the database.
Usage: python seed_scenarios_hprim_cotation.py
"""
import sys
from pathlib import Path
from seed_scenarios_from_json import seed_scenarios_from_json

if __name__ == "__main__":
    # Path to the HPRIM_COTATION scenarios
    seed_path = Path("data/scenario_seeds/scenarios_hprim_cotation.json")
    print(f"Seeding scenarios from {seed_path}...")
    count = seed_scenarios_from_json(seed_path)
    print(f"Total scenarios seeded: {count}")
