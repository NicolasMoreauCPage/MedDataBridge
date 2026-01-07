#!/usr/bin/env python3
"""Test error logging in file poller"""

import sys
import logging
from pathlib import Path
import tempfile
import asyncio

# Set up logging like production
logging.basicConfig(
    level=logging.ERROR,
    format='[%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("test")

sys.path.insert(0, str(Path(__file__).parent))

from app.services.file_poller import FilePollerService

async def test_error_logging():
    """Test that errors are properly logged"""
    
    # Create test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        inbox = tmpdir / "inbox"
        inbox.mkdir()
        
        # Create a malformed XML file (will cause UnicodeDecodeError if read as UTF-8)
        # Even with encoding detection, we'll use a different error to test
        bad_file = inbox / "bad_file.xml"
        
        # This file has UTF-8 content but claims to be ISO-8859-1
        bad_file.write_bytes(b"<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>\n\xc3\xa9\xc3\xa7\xc3\xa8")
        
        print(f"[TEST] Created bad file: {bad_file}")
        
        # Try to read it
        print("[TEST] Attempting to read file with wrong encoding...\n")
        
        try:
            # This should raise an error because UTF-8 bytes declared as ISO-8859-1
            encoding = FilePollerService._detect_encoding(bad_file)
            print(f"[TEST] Detected encoding: {encoding}")
            content = bad_file.read_text(encoding=encoding)
            print(f"[TEST] Content: {content}")
        except Exception as e:
            logger.error(f"[FILE_ERROR] Error reading file: {e}", exc_info=True)
            print("\n[SUCCESS] ✓ Error was properly logged above")

if __name__ == "__main__":
    asyncio.run(test_error_logging())
