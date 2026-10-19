"""Stress and spike load, with host resource capture.

Unlike test_latency.py (budget gates), these characterise behaviour under heavier
and bursty load and record CPU/RAM/DB-connection peaks. They assert only that the
service stays up (bounded error rate), not a latency budget, so they do not fail
on a slow dev host — the numbers go into qa/reports/perf.json for the report.

Opt-in: set QA_RUN_STRESS=1. Local only (resource capture needs docker).
"""

from __future__ import annotations

import json
import os

import pytest

from lib.config import REPORTS_DIR
from lib.load import run_load
from lib.resources import ResourceMonitor

pytestmark = pytest.mark.perf

_results: dict[str, dict] = {}


@pytest.fixture(scope="module", autouse=True)
def _gate_and_report(cfg):
    if os.getenv("QA_RUN_STRESS", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("opt-in: set QA_RUN_STRESS=1 to run stress/spike load")
    if cfg.is_prod:
        pytest.skip("never run stress load against prod")
    yield
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "perf.json"
    prev = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    prev.update(_results)
    path.write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")


def _record(name, result, resources):
    _results[name] = {**result.as_dict(), "resources": resources}


def test_sustained_stress_list_dossiers(cfg, admin):
    """Sustained high load on the dossier list: service stays up (<5% errors), peaks captured."""
    url = f"{cfg.backend_url}/api/v1/dossiers?limit=20"
    with ResourceMonitor() as mon:
        result = run_load("stress_list_dossiers", url, headers=admin.headers,
                          requests=max(1000, cfg.perf_requests * 5), concurrency=max(50, cfg.perf_concurrency * 3))
    _record("stress_list_dossiers", result, mon.as_dict())
    assert result.error_rate <= 0.05, f"error rate {result.error_rate} codes={result.status_codes}"


def test_spike_auth_me(cfg, admin):
    """A sudden burst of 100 concurrent authenticated calls does not error out."""
    url = f"{cfg.backend_url}/api/v1/auth/me"
    with ResourceMonitor() as mon:
        result = run_load("spike_auth_me", url, headers=admin.headers,
                          requests=500, concurrency=100, warmup=0)
    _record("spike_auth_me", result, mon.as_dict())
    assert result.error_rate <= 0.05, f"error rate {result.error_rate} codes={result.status_codes}"
