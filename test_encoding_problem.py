#!/usr/bin/env python3
"""Demonstrate the encoding problem"""

# 1. Create an ISO-8859-1 HPRIM file
iso_content = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<evenementsServeurActes xmlns="http://www.hprim.org/hprimXML">
  <enteteMessage modeTraitement="réel">
    <identifiantMessage>TEST001</identifiantMessage>
  </enteteMessage>
</evenementsServeurActes>'''

from pathlib import Path

# Write as ISO-8859-1
iso_file = Path("test_iso_8859_1.xml")
iso_file.write_text(iso_content, encoding="ISO-8859-1")

print("[STEP 1] Created ISO-8859-1 file")
print(f"  File: {iso_file}")
print(f"  Size: {iso_file.stat().st_size} bytes\n")

# 2. Try to read it as UTF-8 (wrong!)
print("[STEP 2] Reading as UTF-8 (WRONG!):")
try:
    content_utf8 = iso_file.read_text(encoding="UTF-8")
    print(f"  Content (first 200 chars): {content_utf8[:200]}")
    print(f"  Contains 'hprimxml'? {'hprimxml' in content_utf8.lower()}")
    print(f"  Contains 'hprim.org'? {'hprim.org' in content_utf8.lower()}")
except Exception as e:
    print(f"  ERROR: {e}")

print()

# 3. Try to read it with correct encoding (right!)
print("[STEP 3] Reading with ISO-8859-1 (CORRECT!):")
content_iso = iso_file.read_text(encoding="ISO-8859-1")
print(f"  Content (first 200 chars): {content_iso[:200]}")
print(f"  Contains 'hprimxml'? {'hprimxml' in content_iso.lower()}")
print(f"  Contains 'hprim.org'? {'hprim.org' in content_iso.lower()}")

print("\n[CONCLUSION]")
print(f"  If read as UTF-8: HPRIM detection FAILS")
print(f"  If read with ISO-8859-1: HPRIM detection SUCCEEDS")
