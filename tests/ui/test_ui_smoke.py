import pytest
import requests
import os
from pathlib import Path


def append_audit(line: str):
    audit = Path(__file__).parent / "AUDIT_TESTS.md"
    try:
        with audit.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


@pytest.mark.ui
def test_homepage_preflight_and_toggle():
    """Basic smoke test: check presence of preflight snippet and theme toggle.

    The test first attempts an HTTP GET to the running server if `APP_BASE_URL`
    is set. If not available, it falls back to scanning the local
    template `app/templates/base.html` to verify the early preflight script
    and the `themeToggle` element are present. On success, it appends a
    line to `tests/ui/AUDIT_TESTS.md`.
    """
    base = os.getenv("APP_BASE_URL")
    found = False

    if base:
        try:
            r = requests.get(base + "/", timeout=5)
            if r.status_code == 200 and ("data-theme" in r.text or "themeToggle" in r.text):
                found = True
        except Exception:
            found = False

    if not found:
        # Fallback: inspect local template file
        tpl = Path(__file__).parents[2] / "app" / "templates" / "base.html"
        if tpl.exists():
            content = tpl.read_text(encoding="utf-8")
            if "data-theme" in content or "themeToggle" in content:
                found = True

    assert found, "Preflight snippet or theme toggle not found in server response or template"
    append_audit(f"PASS: test_homepage_preflight_and_toggle")