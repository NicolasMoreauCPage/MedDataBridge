#!/usr/bin/env python3
"""
Project-level stub that exposes `seed_hl7_scenarios()` for tests and scripts.

If the richer implementation exists under `scripts/manual/seed_hl7_scenarios.py`,
we forward to it. Otherwise provide a no-op that logs absence of source files.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    # Prefer the maintained script in scripts/manual when available
    from scripts.manual.seed_hl7_scenarios import (
        seed_hl7_scenarios as _seed_impl,
        extract_hl7_messages as extract_hl7_messages,
        extract_trigger_from_message as extract_trigger_from_message,
        get_scenario_name_from_path as get_scenario_name_from_path,
        _save_corrections_report as _save_corrections_report,
    )
except Exception:  # pragma: no cover - defensive fallback
    _seed_impl = None
    extract_hl7_messages = None
    extract_trigger_from_message = None
    get_scenario_name_from_path = None
    _save_corrections_report = None


def seed_hl7_scenarios():
    """Expose seed function for tests.

    If the real implementation is available, call it; otherwise log and no-op.
    """
    if _seed_impl is None:
        logger.warning("seed_hl7_scenarios implementation not available; skipping seed")
        return
    return _seed_impl()


if __name__ == "__main__":
    seed_hl7_scenarios()
