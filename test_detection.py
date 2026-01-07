#!/usr/bin/env python3
"""Test HPRIM detection locally"""
import re
from pathlib import Path

def detect_encoding(file_path):
    """Detect XML encoding"""
    try:
        raw = file_path.read_bytes()[:200]
        match = re.search(br'encoding=["\']([^"\']+)["\']', raw)
        if match:
            encoding = match.group(1).decode('ascii')
            print(f"[ENCODING] {file_path.name}: detected encoding={encoding}")
            return encoding
    except Exception as e:
        print(f"[ENCODING] Error: {e}")
    print(f"[ENCODING] {file_path.name}: using default UTF-8")
    return 'utf-8'

# Test
file_path = Path("test_hprim.xml")
encoding = detect_encoding(file_path)

# Read with detected encoding
content = file_path.read_text(encoding=encoding)
print(f"\n[CONTENT] First 300 chars:\n{content[:300]}\n")

# Test HPRIM detection
content_lower = content.lower()
is_xml = content.strip().startswith('<?xml')
has_hprim = (
    'hprimxml' in content_lower or 
    'hprim.org' in content_lower or
    '<evenementsserveuractes' in content_lower
)
is_hprim = is_xml and has_hprim

print(f"[DETECTION] is_xml={is_xml}, has_hprim={has_hprim}, is_hprim={is_hprim}")
