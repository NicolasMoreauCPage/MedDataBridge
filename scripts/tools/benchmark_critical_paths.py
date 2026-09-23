"""Mesure reproductible des parcours HTTP critiques et vérification de leurs SLO."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


def percentile(values: list[float], rank: float) -> float:
    """Calcule un percentile par interpolation linéaire."""
    if not values:
        raise ValueError("Une série non vide est requise")
    if not 0 <= rank <= 100:
        raise ValueError("Le percentile doit être compris entre 0 et 100")
    ordered = sorted(values)
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


@dataclass
class PathSummary:
    name: str
    method: str
    path: str
    iterations: int
    successes: int
    failures: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    throughput_per_second: float
    average_response_bytes: float
    p50_target_ms: float | None
    p95_target_ms: float | None
    passed: bool
    errors: list[str]


def _request(
    session: requests.Session,
    base_url: str,
    definition: dict[str, Any],
    timeout: float,
) -> tuple[float, int, int]:
    started = time.perf_counter()
    response = session.request(
        definition.get("method", "GET").upper(),
        f"{base_url.rstrip('/')}/{definition['path'].lstrip('/')}",
        params=definition.get("params"),
        json=definition.get("json"),
        headers=definition.get("headers"),
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, response.status_code, len(response.content)


def benchmark_path(
    session: requests.Session,
    base_url: str,
    definition: dict[str, Any],
    *,
    iterations: int,
    timeout: float,
) -> PathSummary:
    """Exécute un parcours, hors requête de chauffe, puis contrôle ses seuils."""
    expected_statuses = set(definition.get("expected_statuses", [200]))
    _request(session, base_url, definition, timeout)

    durations: list[float] = []
    sizes: list[int] = []
    errors: list[str] = []
    total_started = time.perf_counter()
    for index in range(iterations):
        try:
            elapsed_ms, status, size = _request(session, base_url, definition, timeout)
            if status not in expected_statuses:
                errors.append(f"itération {index + 1}: statut HTTP {status}")
                continue
            durations.append(elapsed_ms)
            sizes.append(size)
        except requests.RequestException as exc:
            errors.append(f"itération {index + 1}: {exc}")
    total_seconds = time.perf_counter() - total_started

    p50 = percentile(durations, 50) if durations else float("inf")
    p95 = percentile(durations, 95) if durations else float("inf")
    p50_target = definition.get("p50_ms")
    p95_target = definition.get("p95_ms")
    passed = not errors
    if p50_target is not None:
        passed = passed and p50 <= float(p50_target)
    if p95_target is not None:
        passed = passed and p95 <= float(p95_target)

    return PathSummary(
        name=definition["name"],
        method=definition.get("method", "GET").upper(),
        path=definition["path"],
        iterations=iterations,
        successes=len(durations),
        failures=len(errors),
        p50_ms=round(p50, 3),
        p95_ms=round(p95, 3),
        mean_ms=round(statistics.mean(durations), 3) if durations else float("inf"),
        throughput_per_second=round(len(durations) / total_seconds, 3)
        if total_seconds
        else 0.0,
        average_response_bytes=round(statistics.mean(sizes), 1) if sizes else 0.0,
        p50_target_ms=float(p50_target) if p50_target is not None else None,
        p95_target_ms=float(p95_target) if p95_target is not None else None,
        passed=passed,
        errors=errors,
    )


def run_manifest(
    manifest: dict[str, Any],
    *,
    base_url: str | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Exécute tous les parcours décrits par un manifeste versionné."""
    runtime_session = session or requests.Session()
    iterations = int(manifest.get("iterations", 30))
    if iterations < 2:
        raise ValueError("Au moins deux itérations sont requises")
    timeout = float(manifest.get("timeout_seconds", 60))
    target_url = base_url or manifest.get("base_url", "http://localhost:8000")
    common_headers = manifest.get("headers", {})
    runtime_session.headers.update(common_headers)

    summaries = [
        benchmark_path(
            runtime_session,
            target_url,
            definition,
            iterations=iterations,
            timeout=timeout,
        )
        for definition in manifest.get("paths", [])
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": target_url,
        "environment": manifest.get("environment", {}),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "passed": bool(summaries) and all(summary.passed for summary in summaries),
        "paths": [asdict(summary) for summary in summaries],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark_results/critical-paths.json")
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = run_manifest(manifest, base_url=args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for result in report["paths"]:
        status = "OK" if result["passed"] else "ECHEC"
        print(
            f"[{status}] {result['name']}: p50={result['p50_ms']} ms, p95={result['p95_ms']} ms"
        )
    print(f"Rapport: {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
