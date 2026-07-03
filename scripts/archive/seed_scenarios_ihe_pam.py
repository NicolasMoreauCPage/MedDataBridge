"""
Seed all scenarios for a specific category from a JSON file into the database.
Usage: python seed_scenarios_ihe_pam.py
"""
import sys
from pathlib import Path
from seed_scenarios_from_json import seed_scenarios_from_json

if __name__ == "__main__":
    # Path to the IHE_PAM scenarios
    seed_path = Path("data/scenario_seeds/scenarios_ihe_pam.json")
    print(f"Seeding scenarios from {seed_path}...")
    count = seed_scenarios_from_json(seed_path)
    print(f"Total scenarios seeded: {count}")
