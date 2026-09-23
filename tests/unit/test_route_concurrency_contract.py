"""Regression guards for FastAPI route concurrency contracts."""

import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
ROUTE_ROOTS = (APP_ROOT / "routers", APP_ROOT / "api")
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _is_route(function: ast.AsyncFunctionDef) -> bool:
    for decorator in function.decorator_list:
        candidate = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(candidate, ast.Attribute) and candidate.attr in HTTP_METHODS:
            return True
    return False


def test_sync_database_routes_do_not_use_pointless_async_def():
    """A sync SQLModel route without await must run in FastAPI's thread pool."""
    offenders: list[str] = []
    for root in ROUTE_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.AsyncFunctionDef) or not _is_route(node):
                    continue
                body = ast.get_source_segment(source, node) or ""
                uses_sync_session = (
                    "Depends(get_session)" in body or "Depends(get_db)" in body
                )
                has_await = any(
                    isinstance(child, ast.Await) for child in ast.walk(node)
                )
                if uses_sync_session and not has_await:
                    offenders.append(
                        f"{path.relative_to(APP_ROOT.parent)}:{node.lineno}:{node.name}"
                    )

    assert offenders == [], (
        "Ces routes SQLModel synchrones bloquent inutilement la boucle async; "
        f"les déclarer avec def: {offenders}"
    )
