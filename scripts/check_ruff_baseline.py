"""Empêche l'augmentation progressive de la dette Ruff historique.

Les erreurs d'exécution sont déjà bloquantes séparément. Ce contrôle couvre
l'ensemble de ``app/`` pendant que la dette non critique est réduite par lots.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def ruff_error_count(path: str) -> int:
    """Retourne le nombre d'anomalies Ruff, sans confondre dette et échec outil."""
    result = subprocess.run(
        ["ruff", "check", path, "--output-format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or "ruff n'a pas pu analyser le code")
    return len(json.loads(result.stdout))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="app")
    parser.add_argument("--max-errors", type=int, required=True)
    args = parser.parse_args()

    actual = ruff_error_count(args.path)
    if actual > args.max_errors:
        print(
            f"Dette Ruff en hausse : {actual} anomalies, baseline {args.max_errors}.",
            file=sys.stderr,
        )
        return 1
    print(f"Dette Ruff contrôlée : {actual}/{args.max_errors} anomalies maximum.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
