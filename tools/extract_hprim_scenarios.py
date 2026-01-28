# Script to extract HPRIM scenarios from source .txt files and generate a Python seed list
import os
import json
from pathlib import Path

SRC_DIR = Path("docs/interfaces.integration_src/interfaces.integration/src/main/resources/data/entrant/hprimxml/")
OUT_PATH = Path("data/scenarios_hprim_seed.py")

scenarios = []

def extract_scenarios():
    for fname in sorted(os.listdir(SRC_DIR)):
        if not fname.endswith(".txt"):
            continue
        fpath = SRC_DIR / fname
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
            if not content:
                continue
            scenario = {
                "key": f"hprim_{fname.replace('.txt','').lower()}",
                "name": fname,
                "description": f"Scénario HPRIM extrait de {fname}",
                "category": "HPRIM",
                "protocol": "HPRIM",
                "tags": "hprim,import",
                "steps": [
                    {
                        "order_index": 1,
                        "name": f"Step 1: {fname}",
                        "description": None,
                        "message_format": "hprimxml" if "<evenementsServeurActes" in content or "<" in content[:100] else "hl7",
                        "message_type": None,
                        "payload": content
                    }
                ]
            }
            scenarios.append(scenario)

def write_seed():
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("scenarios = [\n")
        for scen in scenarios:
            f.write(f"    {json.dumps(scen, ensure_ascii=False, indent=4)},\n")
        f.write("]\n")

if __name__ == "__main__":
    extract_scenarios()
    write_seed()
    print(f"{len(scenarios)} scénarios HPRIM extraits et écrits dans {OUT_PATH}")
