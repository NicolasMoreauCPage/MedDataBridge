"""Applique le résultat d'une campagne de round-trip au catalogue courant.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/apply_scenario_catalog_review.py \
        /chemin/vers/result.json
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.db import Session, engine
from app.services.scenario_catalog_review import apply_catalog_review


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply_scenario_catalog_review.py RESULT.json")
    report_path = Path(sys.argv[1]).resolve()
    if not report_path.is_file():
        raise SystemExit(f"Rapport introuvable : {report_path}")
    with Session(engine) as session:
        result = apply_catalog_review(session, report_path)
    print(result)


if __name__ == "__main__":
    main()
