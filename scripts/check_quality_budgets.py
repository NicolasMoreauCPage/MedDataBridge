#!/usr/bin/env python3
"""Contrôles de non-régression de maintenabilité pour le code applicatif.

Les plafonds sont volontairement progressifs : le dépôt contient des workflows
historiques très étendus, mais aucun nouveau dépassement ne peut désormais être
introduit sans rendre la dérogation explicite et temporaire.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

# Les unités existantes sont suivies individuellement jusqu'à leur extraction.
FUNCTION_EXCEPTIONS = {
    ("app/app.py", "create_app"),
    ("app/services/transport_inbound.py", "on_message_inbound_async"),
}

# ``scenarios.py`` reste le point d'entrée historique de plusieurs parcours.
# Son découpage est suivi séparément ; cette dérogation évite qu'un formatage
# mécanique fasse échouer le contrôle pendant l'extraction progressive.
ROUTER_LINE_EXCEPTIONS = {"app/routers/scenarios.py": 2_500}


def _functions(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        (node.name, node.end_lineno - node.lineno + 1)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def main() -> int:
    errors: list[str] = []
    for path in APP.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        lines = len(path.read_text(encoding="utf-8").splitlines())
        router_limit = ROUTER_LINE_EXCEPTIONS.get(relative, 2_000)
        if path.parent.name == "routers" and lines > router_limit:
            errors.append(f"{relative}: router exceeds {router_limit:,} lines ({lines})")
        for name, length in _functions(path):
            if length > 500 and (relative, name) not in FUNCTION_EXCEPTIONS:
                errors.append(f"{relative}:{name} exceeds 500 lines ({length})")
    if errors:
        print("Quality budget exceeded:", *errors, sep="\n- ", file=sys.stderr)
        return 1
    print("Quality budgets passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
