"""The progressive complexity budget must remain executable in CI."""

import subprocess
import sys
from pathlib import Path


def test_quality_budget_script_passes():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/check_quality_budgets.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
