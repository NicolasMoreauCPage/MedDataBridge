"""Contrat du benchmark FHIR utilisé en qualification."""

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/tools/benchmark_fhir_exports.py"
SPEC = importlib.util.spec_from_file_location("benchmark_fhir_exports", SCRIPT_PATH)
benchmark_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark_module
SPEC.loader.exec_module(benchmark_module)


def test_percentile_uses_linear_interpolation():
    assert benchmark_module.percentile([100.0], 95) == 100.0
    assert benchmark_module.percentile([0.0, 100.0], 50) == 50.0
    assert benchmark_module.percentile([0.0, 100.0], 95) == 95.0


def test_venues_benchmark_uses_the_published_route_and_page_contract(monkeypatch):
    class DisabledCache:
        enabled = False

    class Response:
        status_code = 200
        content = b"{}"

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        return Response()

    monkeypatch.setattr(benchmark_module, "get_cache_service", lambda: DisabledCache())
    monkeypatch.setattr(benchmark_module.requests, "get", get)
    benchmark = benchmark_module.FHIRExportBenchmark(base_url="http://bridge.test")

    results = benchmark.benchmark_export(
        "venues",
        ej_id=42,
        iterations=2,
        cache_enabled=False,
        page_limit=250,
    )

    assert len(results) == 2
    assert calls == [
        ("http://bridge.test/api/fhir/export/venues/42", {"limit": 250, "offset": 0}),
        ("http://bridge.test/api/fhir/export/venues/42", {"limit": 250, "offset": 0}),
        ("http://bridge.test/api/fhir/export/venues/42", {"limit": 250, "offset": 0}),
    ]
