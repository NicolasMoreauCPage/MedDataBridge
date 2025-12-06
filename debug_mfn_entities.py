#!/usr/bin/env python3
"""Debug MFN entity extraction."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.mfn_importer import parse_mfn_message

MFN_FILE = Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/MFN/Archive/ExempleExtractionStructure.txt")

content = MFN_FILE.read_text(encoding="utf-8", errors="ignore")
entities = parse_mfn_message(content)

print(f"Total entities parsed: {len(entities)}")

# Count by type
type_counts = {}
for ent in entities:
    t = ent.type_code or "UNKNOWN"
    type_counts[t] = type_counts.get(t, 0) + 1

print("\nEntities by type:")
for t, count in sorted(type_counts.items()):
    print(f"  {t}: {count}")

# Show first 5 entities with details
print("\nFirst 5 entities:")
for i, ent in enumerate(entities[:5]):
    print(f"\n{i+1}. Type: {ent.type_code}, Code: {ent.get('CD')}")
    print(f"   Props: {list(ent.props.keys())[:10]}")
    print(f"   Name: {ent.get('LBL')}")
    print(f"   Parent refs: {ent.parent_refs}")
