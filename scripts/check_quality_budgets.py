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
FUNCTION_EXCEPTIONS: set[tuple[str, str]] = set()

ROUTER_LINE_EXCEPTIONS: dict[str, int] = {}


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
