# Script pour générer les listes de scénarios par catégorie à insérer dans les scripts de seed
import json
from pathlib import Path

DUMP_PATH = Path("data/all_scenarios_dump.json")

with open(DUMP_PATH, encoding="utf-8") as f:
    all_scenarios = json.load(f)

def filter_and_dump(category, out_path):
    scenarios = [s for s in all_scenarios if s.get("category") == category]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("scenarios = [\n")
        for scen in scenarios:
            f.write(f"    {json.dumps(scen, ensure_ascii=False, indent=4)},\n")
        f.write("]\n")

if __name__ == "__main__":
    filter_and_dump("IHE_PAM", "data/scenarios_ihe_pam_seed.py")
    filter_and_dump("HPRIM", "data/scenarios_hprim_seed.py")
    filter_and_dump("HL7", "data/scenarios_hl7_seed.py")
    print("Fichiers de seed générés pour chaque catégorie.")
