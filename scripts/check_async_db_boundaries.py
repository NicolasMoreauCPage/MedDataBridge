#!/usr/bin/env python3
"""Interdit les accès SQL directs dans les routes asynchrones.

Les routes utilisant SQLModel synchrone doivent être des fonctions synchrones
(donc exécutées par FastAPI dans son pool de threads) ou déléguer leur phase
SQL à une session courte hors de la boucle événementielle.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED: set[tuple[str, str]] = set()


def _is_route(node: ast.AsyncFunctionDef) -> bool:
    decorators = " ".join(ast.unparse(item) for item in node.decorator_list)
    return any(
        method in decorators
        for method in (".get(", ".post(", ".put(", ".patch(", ".delete(")
    )


def main() -> int:
    violations: list[str] = []
    for path in (ROOT / "app" / "routers").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef) or not _is_route(node):
                continue
            body = ast.get_source_segment(source, node) or ""
            if "session." in body and (relative, node.name) not in ALLOWED:
                violations.append(f"{relative}:{node.lineno} {node.name}")
    if violations:
        print("New async SQL route(s):", *violations, sep="\n- ", file=sys.stderr)
        return 1
    print("Async SQL boundary budget passed (no tracked exceptions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
