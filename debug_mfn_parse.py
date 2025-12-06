#!/usr/bin/env python3
"""Debug MFN parsing."""
from pathlib import Path

MFN_FILE = Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/MFN/Archive/ExempleExtractionStructure.txt")

content = MFN_FILE.read_text(encoding="utf-8", errors="ignore")
print(f"Original content length: {len(content)}")
print(f"\\r count: {content.count(chr(13))}")
print(f"\\n count: {content.count(chr(10))}")

# Show first 200 chars
print("\nFirst 200 chars:")
print(repr(content[:200]))

# Apply the transformation from parse_mfn_message
text = content.replace("\r", "\n")
lines = [ln for ln in text.split("\n") if ln.strip()]

print(f"\nAfter parsing:")
print(f"Number of lines: {len(lines)}")
print(f"\nFirst 5 lines:")
for i, line in enumerate(lines[:5]):
    print(f"{i+1}: {line[:80]}...")
    
# Count segment types
segments = {}
for line in lines:
    seg = line.split("|", 1)[0] if "|" in line else ""
    segments[seg] = segments.get(seg, 0) + 1

print(f"\nSegment counts:")
for seg, count in sorted(segments.items()):
    if seg:
        print(f"  {seg}: {count}")
