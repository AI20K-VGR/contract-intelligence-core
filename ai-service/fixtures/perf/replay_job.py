"""Replay a stored /jobs/idp request against the local service and summarize the runs.

Run inside the AI2 container (it reads the container env and AI2_DATABASE_URL):

    python -m fixtures.perf.replay_job run --request-file /tmp/ai2-perf/ref-request.json \
        --runs 5 --label p1-baseline
    python -m fixtures.perf.replay_job summarize --label p1-baseline

Writes go through POST /jobs/idp only; every SQL statement here is a read. The local LLM
router (:20128) is the only accepted provider, and no request payload is ever printed.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from app.security.service_envelope import build_service_envelope

SERVICE_URL = "http://127.0.0.1:8002/jobs/idp"
ROUTER_MARK = ":20128"
ROUTER_ENVS = ("AI2_LLM_BASE_URL", "AI2_CONTRACT_GRAPH_PAIRS_BASE_URL")
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "PARTIAL"}
PAIRS_STAGE = "contract_graph_pairs"
POLL_SECONDS = 2.0
RUN_TIMEOUT_SECONDS = 1800.0


def nearest_rank(values: Sequence[float], q: float) -> float | None:
    """Nearest-rank percentile (the debug report's definition); None for no values."""

    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def assert_router(url: str | None) -> None:
    if not url or ROUTER_MARK not in url:
        raise SystemExit(f"refusing to run: LLM base URL is not the local router ({ROUTER_MARK})")


def assert_idle(running: int) -> None:
    if running != 0:
        raise SystemExit(f"refusing to run: {running} AI2 job(s) RUNNING")


def rewrite_request(
    payload: Mapping[str, Any],
    label: str,
    index: int,
    *,
    secret: str,
    now: int | None = None,
) -> dict[str, Any]:
    """Fresh request id/idempotency key and a re-signed envelope for the same dossier."""

    rewritten = copy.deepcopy(dict(payload))
    old = rewritten.pop("service_envelope", None) or {}
    request_id = f"perf-{label}-{index}-{uuid4().hex[:8]}"
    rewritten["request_id"] = request_id
    rewritten["idempotency_key"] = request_id
    rewritten["service_envelope"] = build_service_envelope(
        rewritten,
        secret=secret,
        tenant_id=old.get("tenant_id") or "tenant_a",
        dossier_id=rewritten["dossier_id"],
        actor_id=old.get("actor_id") or "backend",
        issuer=os.getenv("AI2_SERVICE_ISSUER", "backend-service"),
        audience=os.getenv("AI2_SERVICE_AUDIENCE", "vsf-ai2"),
        key_id=os.getenv("AI2_SERVICE_KEY_ID", "default"),
        scopes=old.get("scopes"),
        now=now,
    )
    return rewritten


def _pairs_coverage(coverage: Mapping[str, Any]) -> Mapping[str, Any]:
    return (coverage.get("contract_graph") or {}).get("pairs") or {}


def _percentiles(values: list[float]) -> dict[str, float | None]:
    return {"p50": nearest_rank(values, 50), "p90": nearest_rank(values, 90)}


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate per-job rows ({job_id, status, wall_ms, pairs_ms, stages, coverage})."""

    jobs = []
    for row in rows:
        coverage = row.get("coverage") or {}
        job_timing = coverage.get("job_timing") or {}
        llm_timing = coverage.get("llm_timing") or {}
        pairs = _pairs_coverage(coverage)
        wall, pairs_ms = row.get("wall_ms"), row.get("pairs_ms")
        pipeline = job_timing.get("pipeline_ms")
        jobs.append(
            {
                "job_id": row["job_id"],
                "status": row.get("status"),
                "wall_ms": wall,
                "pairs_ms": pairs_ms,
                "outside_pairs_ms": wall - pairs_ms
                if wall is not None and pairs_ms is not None
                else None,
                "outside_pipeline_ms": wall - pipeline
                if wall is not None and pipeline is not None
                else None,
                "job_timing": job_timing,
                "llm_pairs": (llm_timing.get("by_operation") or {}).get("pairs"),
                "llm_calls": llm_timing.get("llm_calls") or 0,
                "batches_completed": pairs.get("batches_completed"),
                "stopped_reason": pairs.get("stopped_reason"),
                "stages": dict(row.get("stages") or {}),
            }
        )

    def column(key: str) -> list[float]:
        return [job[key] for job in jobs if job[key] is not None]

    return {
        "jobs": jobs,
        "calls": sum(job["llm_calls"] for job in jobs),
        "wall_ms": _percentiles(column("wall_ms")),
        "pairs_ms": _percentiles(column("pairs_ms")),
        "outside_pairs_ms": _percentiles(column("outside_pairs_ms")),
        "outside_pipeline_ms": _percentiles(column("outside_pipeline_ms")),
    }


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.0f}"
    if isinstance(value, Mapping):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = ["| metric | p50 (ms) | p90 (ms) |", "|---|---|---|"]
    for key in ("wall_ms", "pairs_ms", "outside_pairs_ms", "outside_pipeline_ms"):
        stats = summary[key]
        lines.append(f"| {key} | {_cell(stats['p50'])} | {_cell(stats['p90'])} |")
    lines += [
        "",
        "| job_id | status | wall_ms | pairs_ms | wall−pairs | wall−pipeline | job_timing "
        "| llm pairs | batches | stopped_reason |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for job in summary["jobs"]:
        cells = [
            job["job_id"],
            job["status"],
            job["wall_ms"],
            job["pairs_ms"],
            job["outside_pairs_ms"],
            job["outside_pipeline_ms"],
            job["job_timing"] or None,
            job["llm_pairs"],
            job["batches_completed"],
            job["stopped_reason"],
        ]
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines += ["", "| job_id | stage durations (ms) |", "|---|---|"]
    for job in summary["jobs"]:
        lines.append(f"| {job['job_id']} | {_cell(job['stages'] or None)} |")
    lines += ["", f"calls={summary['calls']}"]
    return "\n".join(lines)


# --- database (read-only) and HTTP -------------------------------------------------------


def _engine():
    from app.db.engine import get_engine

    return get_engine()


def _running_jobs(engine) -> int:
    from sqlalchemy import text

    with engine.connect() as cx:
        return int(
            cx.execute(text("select count(*) from ai2.jobs where status='RUNNING'")).scalar()
        )


def _job_by_request(engine, request_id: str) -> tuple[str, str] | None:
    from sqlalchemy import text

    with engine.connect() as cx:
        row = cx.execute(
            text("select job_id, status from ai2.jobs where request_id=:r"), {"r": request_id}
        ).first()
    return (row[0], row[1]) if row else None


def _post(payload: Mapping[str, Any]) -> int:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        SERVICE_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        # Status only: the error body may echo request fields.
        raise SystemExit(f"POST /jobs/idp answered HTTP {exc.code}") from None


def _calls_for(engine, job_ids: Sequence[str]) -> int:
    return summarize_rows(_load_rows(engine, job_ids=job_ids))["calls"]


def run(request_file: str, runs: int, label: str) -> None:
    for name in ROUTER_ENVS:
        assert_router(os.getenv(name))
    secret = os.getenv("AI2_SERVICE_HMAC_SECRET", "")
    if not secret:
        raise SystemExit("AI2_SERVICE_HMAC_SECRET is not set")
    with open(request_file, encoding="utf-8") as handle:
        original = json.loads(handle.read().strip())
    engine = _engine()
    job_ids: list[str] = []
    for index in range(runs):
        assert_idle(_running_jobs(engine))
        payload = rewrite_request(original, label, index, secret=secret)
        _post(payload)
        deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
        job = None
        while time.monotonic() < deadline:
            job = _job_by_request(engine, payload["request_id"])
            if job and job[1] in TERMINAL:
                break
            time.sleep(POLL_SECONDS)
        if not job or job[1] not in TERMINAL:
            raise SystemExit(f"run {index}: job did not finish within {RUN_TIMEOUT_SECONDS:.0f}s")
        job_ids.append(job[0])
        print(f"run={index} job_id={job[0]} status={job[1]}", flush=True)
    print(f"calls={_calls_for(engine, job_ids)}")


def _load_rows(
    engine, *, label: str | None = None, job_ids: Sequence[str] | None = None
) -> list[dict[str, Any]]:
    from sqlalchemy import bindparam, text

    if job_ids is not None:
        query = text(
            "select job_id, status, created_ms, updated_ms, result_json from ai2.jobs "
            "where job_id in :ids order by created_ms"
        ).bindparams(bindparam("ids", expanding=True))
        params: dict[str, Any] = {"ids": list(job_ids)}
    else:
        query = text(
            "select job_id, status, created_ms, updated_ms, result_json from ai2.jobs "
            "where request_id like :pattern order by created_ms"
        )
        params = {"pattern": f"perf-{label}-%"}
    stage_query = text(
        "select stage_id, duration_ms from ai2.ai2_processing_trace_events "
        "where job_id=:job and duration_ms is not null order by sequence"
    )
    rows = []
    with engine.connect() as cx:
        for job_id, status, created_ms, updated_ms, result_json in cx.execute(query, params):
            stages: dict[str, int] = {}
            for stage_id, duration_ms in cx.execute(stage_query, {"job": job_id}):
                stages[stage_id] = int(duration_ms)
            result = json.loads(result_json) if result_json else {}
            rows.append(
                {
                    "job_id": job_id,
                    "status": status,
                    "wall_ms": int(updated_ms) - int(created_ms),
                    "pairs_ms": stages.get(PAIRS_STAGE),
                    "stages": stages,
                    "coverage": (result.get("contribution") or {}).get("coverage") or {},
                }
            )
    return rows


def summarize(label: str) -> None:
    print(render_markdown(summarize_rows(_load_rows(_engine(), label=label))))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_cmd = commands.add_parser("run")
    run_cmd.add_argument("--request-file", required=True)
    run_cmd.add_argument("--runs", type=int, default=5)
    run_cmd.add_argument("--label", required=True)
    summarize_cmd = commands.add_parser("summarize")
    summarize_cmd.add_argument("--label", required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        if args.runs < 1:
            parser.error("--runs must be >= 1")
        run(args.request_file, args.runs, args.label)
    else:
        summarize(args.label)


if __name__ == "__main__":
    main(sys.argv[1:])
