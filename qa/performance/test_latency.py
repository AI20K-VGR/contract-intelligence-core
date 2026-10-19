"""Performance: latency and throughput of the read paths under concurrent load.

Budgets come from QA_PERF_* (see lib/config.py). Every scenario's numbers are
written to qa/reports/perf.json for the report, pass or fail.

These measure the API tier (FastAPI + Postgres + JWT check). OCR and AI2 run
asynchronously behind Kafka, so their timing is measured end to end in
e2e/test_upload_pipeline.py instead.
"""

from __future__ import annotations

import json

import pytest

from lib.config import REPORTS_DIR
from lib.load import LoadResult, run_load

pytestmark = pytest.mark.perf

_results: dict[str, dict] = {}


@pytest.fixture(scope="module", autouse=True)
def _write_report():
    yield
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "perf.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    previous.update(_results)
    path.write_text(json.dumps(previous, indent=2, ensure_ascii=False), encoding="utf-8")


def _record(result: LoadResult, budget_p95_ms: float | None) -> LoadResult:
    _results[result.name] = {**result.as_dict(), "budget_p95_ms": budget_p95_ms}
    return result


def _check(result: LoadResult, budget_p95_ms: float, max_error_rate: float) -> None:
    assert result.error_rate <= max_error_rate, (
        f"{result.name}: error rate {result.error_rate} codes={result.status_codes}"
    )
    assert result.p95_ms <= budget_p95_ms, f"{result.name}: p95 {result.p95_ms} ms > budget {budget_p95_ms} ms"


@pytest.fixture(scope="module")
def sample_ids(api, admin):
    listing = api.get("/api/v1/dossiers", headers=admin.headers, params={"limit": 20}).json()["data"]
    items = listing if isinstance(listing, list) else listing.get("items", [])
    dossier_id = items[0]["id"] if items else None
    document_id = None
    for item in items:
        docs = api.get(f"/api/v1/dossiers/{item['id']}/documents", headers=admin.headers)
        data = docs.json().get("data") if docs.status_code == 200 else None
        rows = data if isinstance(data, list) else (data or {}).get("items", [])
        if rows:
            dossier_id, document_id = item["id"], rows[0]["id"]
            break
    return {"dossier_id": dossier_id, "document_id": document_id}


def test_perf_health(cfg):
    """GET /health: p95 within the health budget at configured concurrency."""
    r = _record(
        run_load("health", f"{cfg.backend_url}/health", requests=cfg.perf_requests, concurrency=cfg.perf_concurrency),
        cfg.perf_health_p95_ms,
    )
    _check(r, cfg.perf_health_p95_ms, cfg.perf_max_error_rate)


def test_perf_auth_me(cfg, admin):
    """GET /auth/me (JWT verification path): p95 within the API budget."""
    r = _record(
        run_load(
            "auth_me",
            f"{cfg.backend_url}/api/v1/auth/me",
            headers=admin.headers,
            requests=cfg.perf_requests,
            concurrency=cfg.perf_concurrency,
        ),
        cfg.perf_api_p95_ms,
    )
    _check(r, cfg.perf_api_p95_ms, cfg.perf_max_error_rate)


def test_perf_list_dossiers(cfg, admin):
    """GET /dossiers?limit=20 (DB list + ACL): p95 within the API budget."""
    r = _record(
        run_load(
            "list_dossiers",
            f"{cfg.backend_url}/api/v1/dossiers?limit=20",
            headers=admin.headers,
            requests=cfg.perf_requests,
            concurrency=cfg.perf_concurrency,
        ),
        cfg.perf_api_p95_ms,
    )
    _check(r, cfg.perf_api_p95_ms, cfg.perf_max_error_rate)


def test_perf_list_runs(cfg, admin):
    """GET /runs: p95 within the API budget."""
    r = _record(
        run_load(
            "list_runs",
            f"{cfg.backend_url}/api/v1/runs",
            headers=admin.headers,
            requests=cfg.perf_requests,
            concurrency=cfg.perf_concurrency,
        ),
        cfg.perf_api_p95_ms,
    )
    _check(r, cfg.perf_api_p95_ms, cfg.perf_max_error_rate)


def test_perf_dossier_detail(cfg, admin, sample_ids):
    """GET /dossiers/{id}: p95 within the API budget."""
    if not sample_ids["dossier_id"]:
        pytest.skip("no dossier to read")
    r = _record(
        run_load(
            "dossier_detail",
            f"{cfg.backend_url}/api/v1/dossiers/{sample_ids['dossier_id']}",
            headers=admin.headers,
            requests=cfg.perf_requests,
            concurrency=cfg.perf_concurrency,
        ),
        cfg.perf_api_p95_ms,
    )
    _check(r, cfg.perf_api_p95_ms, cfg.perf_max_error_rate)


def test_perf_document_lines(cfg, admin, sample_ids):
    """GET /documents/{id}/lines (all OCR lines in one request): p95 within 2x the API budget."""
    if not sample_ids["document_id"]:
        pytest.skip("no OCR'd document to read")
    budget = cfg.perf_api_p95_ms * 2
    r = _record(
        run_load(
            "document_lines",
            f"{cfg.backend_url}/api/v1/documents/{sample_ids['document_id']}/lines",
            headers=admin.headers,
            requests=max(50, cfg.perf_requests // 4),
            concurrency=max(5, cfg.perf_concurrency // 2),
        ),
        budget,
    )
    _check(r, budget, cfg.perf_max_error_rate)


@pytest.mark.parametrize("concurrency", [1, 10, 50])
def test_perf_scaling_list_dossiers(cfg, admin, concurrency):
    """Throughput/latency of the dossier list as concurrency grows (1 -> 10 -> 50); no errors allowed."""
    r = _record(
        run_load(
            f"scaling_list_dossiers_c{concurrency}",
            f"{cfg.backend_url}/api/v1/dossiers?limit=20",
            headers=admin.headers,
            requests=max(100, concurrency * 5),
            concurrency=concurrency,
        ),
        None,
    )
    assert r.error_rate <= cfg.perf_max_error_rate, r.status_codes


def test_perf_unauthenticated_flood_is_cheap(cfg):
    """Rejected (401) requests stay fast: an anonymous flood cannot tie up the API."""
    r = _record(
        run_load(
            "anon_401_flood",
            f"{cfg.backend_url}/api/v1/auth/me",
            requests=cfg.perf_requests,
            concurrency=cfg.perf_concurrency,
        ),
        cfg.perf_health_p95_ms,
    )
    assert set(r.status_codes) == {"401"}, r.status_codes
    assert r.p95_ms <= cfg.perf_health_p95_ms
