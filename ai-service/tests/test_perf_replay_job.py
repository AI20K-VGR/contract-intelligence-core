"""P1: the perf replay harness computes percentiles, re-signs requests and refuses unsafe runs."""

from __future__ import annotations

import time

import pytest
from test_a1_query_digest import _body_only_request

from app.security.service_envelope import verify_service_envelope
from fixtures.perf import replay_job


def test_nearest_rank_matches_the_debug_report_wall_times() -> None:
    walls = [156.4, 86.0, 115.5, 101.4, 112.3]
    assert replay_job.nearest_rank(walls, 50) == 112.3
    assert replay_job.nearest_rank(walls, 90) == 156.4
    assert replay_job.nearest_rank([], 50) is None


def test_rewritten_request_verifies_with_a_fresh_identity(monkeypatch) -> None:
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    original = _body_only_request()
    now = int(time.time())

    rewritten = replay_job.rewrite_request(
        original, "p1-baseline", 2, secret="test-secret", now=now
    )

    assert rewritten["request_id"].startswith("perf-p1-baseline-2-")
    assert len(rewritten["request_id"]) == len("perf-p1-baseline-2-") + 8
    assert rewritten["idempotency_key"] == rewritten["request_id"]
    assert rewritten["request_id"] != original["request_id"]
    envelope = verify_service_envelope(rewritten, now=now)
    assert envelope.tenant_id == original["service_envelope"]["tenant_id"]
    assert envelope.dossier_id == original["dossier_id"]
    assert original["service_envelope"]["nonce"] != rewritten["service_envelope"]["nonce"]


def test_harness_refuses_a_non_router_base_url() -> None:
    with pytest.raises(SystemExit):
        replay_job.assert_router("https://api.openai.com/v1")
    replay_job.assert_router("http://host.docker.internal:20128/v1")


def test_harness_refuses_while_a_job_is_running() -> None:
    with pytest.raises(SystemExit):
        replay_job.assert_idle(1)
    replay_job.assert_idle(0)


def test_summarize_rows_reports_wall_pairs_and_calls() -> None:
    rows = [
        {
            "job_id": f"job_{i}",
            "status": "SUCCEEDED",
            "wall_ms": wall,
            "pairs_ms": pairs,
            "stages": {"contract_graph_pairs": pairs},
            "coverage": {
                "job_timing": {"snapshot_load_ms": 10, "claim_ms": 5, "pipeline_ms": wall - 900},
                "llm_timing": {
                    "llm_calls": 8,
                    "llm_ms_total": 1,
                    "cached_tokens": None,
                    "by_operation": {
                        "pairs": {"llm_calls": 5, "llm_ms_total": pairs, "llm_ms_max": 9000}
                    },
                },
                "contract_graph": {"pairs": {"batches_completed": 5, "stopped_reason": None}},
            },
        }
        for i, (wall, pairs) in enumerate([(100_000, 90_000), (120_000, 100_000)])
    ]

    summary = replay_job.summarize_rows(rows)

    assert summary["calls"] == 16
    assert summary["wall_ms"] == {"p50": 100_000, "p90": 120_000}
    assert summary["pairs_ms"] == {"p50": 90_000, "p90": 100_000}
    assert summary["outside_pairs_ms"] == {"p50": 10_000, "p90": 20_000}
    assert summary["outside_pipeline_ms"] == {"p50": 900, "p90": 900}
    assert "calls=16" in replay_job.render_markdown(summary)
