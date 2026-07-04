"""
Compatibility shim to run the MFN roundtrip script used by tests.

Invoke as: TESTING=1 python3 scripts/mfn_roundtrip.py
This delegates to scripts.utils.mfn_roundtrip.main() if available.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.utils.mfn_roundtrip import main
except Exception as e:
    print(f"mfn_roundtrip shim: unable to import implementation: {e}")
    raise

if __name__ == '__main__':
    main()
