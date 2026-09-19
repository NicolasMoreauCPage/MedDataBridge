"""Génère un inventaire Markdown des opérations réellement exposées par OpenAPI."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any


def render_inventory(openapi: dict[str, Any] | None = None) -> str:
    """Retourne l'inventaire trié par tag et opération HTTP.

    ``openapi`` est injectable pour vérifier le rendu sans initialiser toute
    l'application. Lors de l'exécution normale, le contrat de l'application
    montée est utilisé.
    """
    if openapi is None:
        from app.app import app

        openapi = app.openapi()

    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path, methods in openapi.get("paths", {}).items():
        for method, operation in methods.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            summary = operation.get("summary") or operation.get("operationId") or "Sans libellé"
            for tag in operation.get("tags") or ["Sans tag"]:
                grouped[tag].append((method.upper(), path, summary))

    count = sum(len(items) for items in grouped.values())
    lines = ["# Inventaire OpenAPI", "", f"{count} opérations générées automatiquement.", ""]
    for tag in sorted(grouped, key=str.lower):
        lines.extend([f"## {tag}", "", "| Méthode | Chemin | Opération |", "|---|---|---|"])
        for method, path, summary in sorted(grouped[tag], key=lambda item: (item[1], item[0])):
            lines.append(f"| `{method}` | `{path}` | {summary} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fichier Markdown de sortie (stdout par défaut)")
    args = parser.parse_args()
    inventory = render_inventory()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(inventory, encoding="utf-8")
    else:
        print(inventory)


if __name__ == "__main__":
    main()
