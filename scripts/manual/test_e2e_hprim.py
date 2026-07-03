#!/usr/bin/env python3
"""Full end-to-end test of HPRIM file detection"""

import sys
import logging
from pathlib import Path
import tempfile
import asyncio

# Set up logging like production
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test")

# Test the actual service code
sys.path.insert(0, str(Path(__file__).parent))

from app.services.file_poller import FilePollerService

async def test_hprim_detection():
    """Test HPRIM detection with ISO-8859-1 file"""
    
    # Create test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        inbox = tmpdir / "inbox"
        inbox.mkdir()
        
        # Create ISO-8859-1 HPRIM file
        hprim_content = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<evenementsServeurActes xmlns="http://www.hprim.org/hprimXML">
  <enteteMessage modeTraitement="réel">
    <identifiantMessage>TEST001</identifiantMessage>
  </enteteMessage>
</evenementsServeurActes>'''
        
        hprim_file = inbox / "test_hprim.xml"
        hprim_file.write_text(hprim_content, encoding="ISO-8859-1")
        
        print(f"[TEST] Created HPRIM file: {hprim_file}")
        print(f"[TEST] File size: {hprim_file.stat().st_size} bytes\n")
        
        # Test encoding detection
        print("[TEST] Testing _detect_encoding()...")
        encoding = FilePollerService._detect_encoding(hprim_file)
        print(f"[TEST] Detected encoding: {encoding}\n")
        
        # Test reading with detected encoding
        print("[TEST] Reading file with detected encoding...")
        try:
            content = hprim_file.read_text(encoding=encoding)
            print(f"[TEST] Successfully read {len(content)} characters")
            print(f"[TEST] Content starts with: {content[:100]}\n")
            
            # Test HPRIM detection
            print("[TEST] Testing HPRIM detection...")
            content_lower = content.lower()
            is_xml = content.strip().startswith('<?xml')
            has_hprim = (
                'hprimxml' in content_lower or 
                'hprim.org' in content_lower or
                '<evenementsserveuractes' in content_lower
            )
            is_hprim = is_xml and has_hprim
            
            print(f"[TEST] is_xml: {is_xml}")
            print(f"[TEST] has_hprim: {has_hprim}")
            print(f"[TEST] is_hprim: {is_hprim}\n")
            
            if is_hprim:
                print("[SUCCESS] ✓ HPRIM file correctly detected!")
            else:
                print("[FAILURE] ✗ HPRIM file NOT detected!")
                print(f"[DEBUG] Content lower has 'hprimxml': {'hprimxml' in content_lower}")
                print(f"[DEBUG] Content lower has 'hprim.org': {'hprim.org' in content_lower}")
                print(f"[DEBUG] Content lower has '<evenementsserveuractes': {'<evenementsserveuractes' in content_lower}")
        
        except Exception as e:
            print(f"[FAILURE] Error reading file: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_hprim_detection())
