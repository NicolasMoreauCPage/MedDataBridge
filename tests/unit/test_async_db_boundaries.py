"""The async/SQL boundary guard must run in a clean Python process."""

import subprocess
import sys
from pathlib import Path


def test_async_db_boundary_guard_passes():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/check_async_db_boundaries.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
