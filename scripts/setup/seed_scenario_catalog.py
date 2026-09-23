#!/usr/bin/env python3
"""Installe explicitement le catalogue de qualification versionné.

Pré-requis : la base ciblée a déjà reçu ``alembic upgrade head``. Le script
est idempotent : il ajoute seulement les thèmes, scénarios et revues absents.

Usage::

    python scripts/setup/seed_scenario_catalog.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import inspect


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import engine  # noqa: E402
from app.services.scenario_catalog_seed import apply_catalog_seed  # noqa: E402


def main() -> int:
    with engine.begin() as connection:
        if "interopscenario" not in inspect(connection).get_table_names():
            print(
                "Le schéma n'est pas migré. Exécutez d'abord `alembic upgrade head`.",
                file=sys.stderr,
            )
            return 2
        created = apply_catalog_seed(connection)

    print(json.dumps(created, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
