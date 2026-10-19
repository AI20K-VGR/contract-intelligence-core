"""Document-pipeline throughput: many dossiers uploaded at once.

Measures the end-to-end latency (upload -> PENDING_REVIEW) when several dossiers
are submitted concurrently, and how it degrades versus a single upload. Records
per-dossier timing, stage latencies and host resource peaks into perf.json.

Opt-in: QA_RUN_PIPELINE=1 and QA_RUN_STRESS=1. Local free mode strongly
recommended (each upload runs OCR + AI2). Deletes every dossier it creates.
Multi-page / 50 MB variants are left as documented manual runs (see report).
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from lib.config import REPORTS_DIR
from lib.pdf import sample_contract_pdf
from lib.resources import ResourceMonitor

pytestmark = pytest.mark.perf

TERMINAL = {"pending_review", "approved", "completed", "failed", "cancelled"}


@pytest.fixture(scope="module")
def _gate(cfg):
    if not cfg.run_pipeline or os.getenv("QA_RUN_STRESS", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("opt-in: set QA_RUN_PIPELINE=1 and QA_RUN_STRESS=1")
    if cfg.is_prod:
        pytest.skip("never run pipeline load against prod")


def _upload_and_wait(api, headers, cfg, name) -> dict:
    t0 = time.perf_counter()
    r = api.post(
        "/api/v1/dossiers",
        headers=headers,
        files=[("contract", ("tp.pdf", sample_contract_pdf(), "application/pdf")),
               ("metadata", (None, json.dumps({"name": name})))],
    )
    upload_ms = (time.perf_counter() - t0) * 1000
    if r.status_code != 202:
        return {"ok": False, "status_code": r.status_code}
    dossier_id = r.json()["data"]["dossier_id"]
    deadline = time.monotonic() + cfg.pipeline_timeout_s
    status = None
    while time.monotonic() < deadline:
        status = (api.get(f"/api/v1/dossiers/{dossier_id}", headers=headers).json()["data"]["latest_job_status"] or "").lower()
        if status in TERMINAL:
            break
        time.sleep(1)
    return {"ok": status in {"pending_review", "approved", "completed"}, "dossier_id": dossier_id,
            "upload_ms": round(upload_ms, 1), "total_s": round(time.perf_counter() - t0, 2), "status": status}


def test_concurrent_pipeline_throughput(_gate, api, operator, admin, cfg):
    """Upload N dossiers concurrently; all reach PENDING_REVIEW, record throughput + resources."""
    n = int(os.getenv("QA_PIPELINE_N", "8"))
    created: list[str] = []
    try:
        with ResourceMonitor() as mon:
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=n) as pool:
                results = list(pool.map(
                    lambda i: _upload_and_wait(api, operator.headers, cfg, f"QA throughput {i}"), range(n)
                ))
            wall = time.perf_counter() - started
        created = [r["dossier_id"] for r in results if r.get("dossier_id")]
        ok = [r for r in results if r.get("ok")]
        durations = sorted(r["total_s"] for r in ok)
        summary = {
            "dossiers": n,
            "succeeded": len(ok),
            "wall_s": round(wall, 2),
            "throughput_dossiers_per_min": round(len(ok) / wall * 60, 1) if wall else 0,
            "per_dossier_s_min": durations[0] if durations else None,
            "per_dossier_s_median": durations[len(durations) // 2] if durations else None,
            "per_dossier_s_max": durations[-1] if durations else None,
            "resources": mon.as_dict(),
        }
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / "perf.json"
        prev = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        prev["pipeline_throughput"] = summary
        path.write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
        assert len(ok) == n, f"only {len(ok)}/{n} dossiers reached PENDING_REVIEW: {[r.get('status') for r in results]}"
    finally:
        for dossier_id in created:
            api.delete(f"/api/v1/dossiers/{dossier_id}", headers=admin.headers)
