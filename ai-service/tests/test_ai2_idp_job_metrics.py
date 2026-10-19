"""Cost and speed of AI2 processing jobs (conflict search) reach Prometheus.

The job child sends one summary over its pipe; the API process records it.
No paid call: usage comes from synthetic traces.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from prometheus_client import REGISTRY

from app.api import main
from app.llm import metrics, usage_ledger
from app.pipeline.job_metrics import build_idp_summary

AI_SERVICE = Path(__file__).resolve().parents[1]


def _value(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture
def metrics_on(monkeypatch):
    monkeypatch.setenv("AI2_METRICS_PORT", "9109")


def _summary(status="SUCCEEDED"):
    return build_idp_summary(
        status=status,
        timing={
            "snapshot_load_ms": 2_000,
            "claim_ms": 50,
            "pipeline_ms": 60_000,
            "persist_ms": 950,
        },
        llm_timing={
            "by_operation": {
                "pair_classifier": {"llm_calls": 4, "llm_ms_total": 20_000},
                "frame_extraction": {"llm_calls": 2, "llm_ms_total": 6_000},
            }
        },
        chat_usage={
            "gpt-5.5": {"calls": 6, "input": 8_000, "input_cached": 2_000, "output": 1_000}
        },
        embedding_tokens=50_000,
        wire={
            "status": "SUCCEEDED",
            "result": {"findings": [{}, {}, {}], "context_findings": [{}]},
        },
    )


# Top-level so the spawned child can import them.
def _claim_then_summary(job_id, payload, conn):
    conn.send(("token-1", "tenant-a", "dossier-a"))
    conn.send(
        (
            "ai2.metrics",
            {
                "status": "SUCCEEDED",
                "duration_seconds": 42.0,
                "phases": {"pipeline": 40.0},
                "findings": {"finding": 2},
            },
        )
    )


def _crash_after_claim(job_id, payload, conn):
    conn.send(("token-1", "tenant-a", "dossier-a"))
    os._exit(137)


def test_usage_ledger_counts_every_client_and_reports_a_delta():
    mark = usage_ledger.snapshot()
    usage_ledger.record_trace(
        {
            "model": "gpt-5.5",
            "served_model": "gpt-5.5-2026-09-01",
            "prompt_tokens": 1_000,
            "cached_tokens": 400,
            "completion_tokens": 200,
            "http_calls": 1,
            "latency_ms": 900.0,
        }
    )
    usage_ledger.record_trace(
        {"model": "gpt-5.5", "error_type": "APITimeoutError", "http_calls": 1}
    )
    delta = usage_ledger.usage_since(mark)
    assert delta["gpt-5.5-2026-09-01"]["input"] == 600
    assert delta["gpt-5.5-2026-09-01"]["input_cached"] == 400
    assert delta["gpt-5.5-2026-09-01"]["output"] == 200
    assert delta["gpt-5.5"] == {
        "calls": 1,
        "errors": 1,
        "input": 0,
        "input_cached": 0,
        "output": 0,
        "latency_ms": 0,
    }


def test_summary_prices_tokens_and_counts_findings():
    summary = _summary()
    assert summary["duration_seconds"] == pytest.approx(63.0)
    assert summary["phases"]["pipeline"] == pytest.approx(60.0)
    assert summary["operations"]["pair_classifier"] == {"calls": 4, "seconds": 20.0}
    chat, embedding = summary["models"]
    # gpt-5.5: 8k input × $5 + 2k cached × $0.5 + 1k output × $30 per 1M tokens
    assert chat["cost"] == pytest.approx(0.04 + 0.001 + 0.03)
    assert embedding["kind"] == "embedding" and embedding["cost"] == pytest.approx(0.001)
    assert summary["findings"] == {"finding": 3, "context_finding": 1}


def test_record_idp_job_feeds_the_ai2_idp_metrics(metrics_on):
    before = {
        "jobs": _value("ai2_idp_jobs_total", status="SUCCEEDED"),
        "cost": _value("ai2_idp_cost_usd_total", kind="chat", model="gpt-5.5"),
        "llm_s": _value("ai2_idp_llm_seconds_total", operation="pair_classifier"),
        "findings": _value("ai2_idp_findings_total", kind="finding"),
        "durations": _value("ai2_idp_job_duration_seconds_count"),
    }
    metrics.record_idp_job(_summary())
    assert _value("ai2_idp_jobs_total", status="SUCCEEDED") == before["jobs"] + 1
    assert _value("ai2_idp_cost_usd_total", kind="chat", model="gpt-5.5") == pytest.approx(
        before["cost"] + 0.071
    )
    assert _value("ai2_idp_llm_seconds_total", operation="pair_classifier") == before["llm_s"] + 20
    assert _value("ai2_idp_findings_total", kind="finding") == before["findings"] + 3
    assert _value("ai2_idp_job_duration_seconds_count") == before["durations"] + 1


def test_record_idp_job_keeps_labels_bounded(metrics_on):
    metrics.record_idp_job(
        {"status": "drop table", "operations": {"Contract 12 of tenant X": {"calls": 1}}}
    )
    assert _value("ai2_idp_jobs_total", status="OTHER") >= 1
    assert _value("ai2_idp_llm_calls_total", operation="other") >= 1


class _Store:
    def __init__(self):
        self.failed = []

    def set_wire(self, job_id, **kwargs):
        self.failed.append((job_id, kwargs))

    def fail_unclaimed(self, job_id, update):
        self.failed.append((job_id, update))

    def get(self, job_id, **_kw):
        return {"tenant_id": "tenant-a", "dossier_id": "dossier-a", "wire": {"job_id": job_id}}


@pytest.fixture
def store(monkeypatch):
    fake = _Store()
    monkeypatch.setattr(main, "JOB_STORE", fake)
    monkeypatch.setattr(main.ProcessingTraceStore, "finalize_stale_job", lambda self, job_id: 0)
    monkeypatch.setattr(main, "_refresh_query_store", lambda job_id: None)
    return fake


def _budget(seconds):
    return {"policy_flags": {"budget_limits": {"max_processing_seconds": seconds}}}


def test_the_api_process_records_the_summary_its_job_child_sends(store, metrics_on):
    before = _value("ai2_idp_findings_total", kind="finding")
    jobs = _value("ai2_idp_jobs_total", status="SUCCEEDED")
    main._run_isolated_job("job-m1", _budget(30), target=_claim_then_summary)
    assert store.failed == []
    assert _value("ai2_idp_jobs_total", status="SUCCEEDED") == jobs + 1
    assert _value("ai2_idp_findings_total", kind="finding") == before + 2


def test_a_killed_job_child_still_counts_as_a_failed_job(store, metrics_on):
    failed = _value("ai2_idp_jobs_total", status="FAILED")
    main._run_isolated_job("job-m2", _budget(30), target=_crash_after_claim)
    assert _value("ai2_idp_jobs_total", status="FAILED") == failed + 1


def test_ai2_imports_without_ai1_code():
    """The AI2 image ships app/ only: no module of AI2 may import contract_ocr (#137)."""
    probe = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'contract_ocr' or name.startswith('contract_ocr.'):\n"
        "            raise ModuleNotFoundError(\"No module named 'contract_ocr'\")\n"
        "sys.meta_path.insert(0, Block())\n"
        "import app.llm.client, app.llm.observability, app.llm.metrics, app.llm.embeddings\n"
        "import app.pipeline.job_metrics, app.api.main\n"
        "print('ok')\n"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LANGFUSE_", "AI2_METRICS"))}
    env["PYTHONPATH"] = str(AI_SERVICE)
    done = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=AI_SERVICE,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip().endswith("ok")
