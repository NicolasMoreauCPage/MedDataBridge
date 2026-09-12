"""Importe le catalogue PAM/HPRIM historique dans la base configurée.

Usage: PYTHONPATH=. .venv/bin/python scripts/import_legacy_pam_hprim_catalog.py
"""
from pathlib import Path

from app.db import Session, engine
from app.services.legacy_scenario_catalog import import_legacy_catalog
from data.scenarios_hprim_seed import scenarios as hprim_scenarios


with Session(engine) as session:
    import json
    pam_raw = json.loads(Path("data/all_scenarios_dump.json").read_text(encoding="utf-8"))
    pam_scenarios = pam_raw.get("scenarios", pam_raw) if isinstance(pam_raw, dict) else pam_raw
    report = import_legacy_catalog(session, pam_scenarios + hprim_scenarios)
print(report)
