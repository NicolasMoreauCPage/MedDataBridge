import importlib.util
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts/tools/benchmark_critical_paths.py"
)
SPEC = importlib.util.spec_from_file_location("benchmark_critical_paths", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    status_code = 200
    content = b"{}"


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse()


def test_percentile_uses_linear_interpolation():
    assert MODULE.percentile([0.0, 100.0], 50) == 50.0
    assert MODULE.percentile([0.0, 100.0], 95) == 95.0


def test_manifest_produces_a_machine_readable_slo_report(monkeypatch):
    ticks = iter([0.0, 0.01, 1.0, 1.1, 1.2, 2.0, 2.2, 3.0])
    monkeypatch.setattr(MODULE.time, "perf_counter", lambda: next(ticks))
    session = FakeSession()
    report = MODULE.run_manifest(
        {
            "iterations": 2,
            "headers": {"X-Test": "qualification"},
            "paths": [
                {
                    "name": "health",
                    "path": "/health",
                    "p50_ms": 200,
                    "p95_ms": 250,
                }
            ],
        },
        base_url="http://bridge.test",
        session=session,
    )

    assert report["passed"] is True
    assert report["paths"][0]["successes"] == 2
    assert report["paths"][0]["p50_ms"] == 150.0
    assert session.headers["X-Test"] == "qualification"
    assert all(call[1] == "http://bridge.test/health" for call in session.calls)


def test_manifest_fails_when_p95_exceeds_target(monkeypatch):
    ticks = iter([0.0, 0.01, 1.0, 1.1, 1.5, 2.0, 2.5, 3.0])
    monkeypatch.setattr(MODULE.time, "perf_counter", lambda: next(ticks))
    report = MODULE.run_manifest(
        {
            "iterations": 2,
            "paths": [{"name": "slow", "path": "/slow", "p95_ms": 100}],
        },
        session=FakeSession(),
    )
    assert report["passed"] is False
    assert report["paths"][0]["p95_ms"] > 100
