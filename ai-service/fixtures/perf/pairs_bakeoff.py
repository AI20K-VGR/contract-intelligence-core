"""Staged bake-off of pairs call settings (P3, plan 261017-1821). Run inside the AI2 container:

    python -m fixtures.perf.pairs_bakeoff trial --candidate C1 --request-file F --run R
    python -m fixtures.perf.pairs_bakeoff rank --run R [--incumbent C0]
    python -m fixtures.perf.pairs_bakeoff drift --run R --candidate C1 [--incumbent C0]
    python -m fixtures.perf.pairs_bakeoff gate --candidate C1
    python -m fixtures.perf.pairs_bakeoff confirm-openai --candidate C1 --user-permission YYYY-MM-DD \
        --dossier HD-TEST-2026-00X

Candidates are deltas on the incumbent: C0 incumbent, C1 ``AI2_PAIRS_REASONING_EFFORT=low``,
C2 ``PAIRS_PER_CALL=10``, C3 ``AI2_CONTRACT_GRAPH_PAIRS_MODEL=gh/gpt-5-mini``. Every command but
``confirm-openai`` refuses a provider that is not the local router (:20128) and prints the host to
stderr; ``confirm-openai`` is the only path to OpenAI and needs today's date as explicit user
permission plus ``AI2_PERF_PROVIDER=openai`` (D10/D13). ``trial`` prints exactly one number, the
job wall in seconds (the ``pipeline`` span, run_idp in-process, nothing written to the DB), and
appends one row to ``$AI2_PERF_DIR/bakeoff-<run>.jsonl`` (outside the repo, no model output).
Every other command prints ``calls=<HTTP requests sent>``.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import random
import statistics
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.llm.client import NineRouterClient
from app.pipeline.contract_graph import pair_classifier as pc
from app.pipeline.contract_graph.model_family import classifier_family_ok, model_name
from app.pipeline.runtime import ProcessingRuntime
from fixtures.perf.replay_job import ROUTER_ENVS, assert_router, nearest_rank, rewrite_request

EFFORT_ENV = "AI2_PAIRS_REASONING_EFFORT"
PAIRS_MODEL_ENV = "AI2_CONTRACT_GRAPH_PAIRS_MODEL"
C3_MODEL = "gh/gpt-5-mini"
C2_BATCH = 10
# The labeler of the pairs gold set (docs/ai2/AI2-20-contract-graph-pairs.vi.md): never a classifier.
LABELER_MODEL = "gpt-4o-mini-2024-07-18"
CANDIDATES: dict[str, dict[str, Any]] = {
    "C0": {},
    "C1": {"env": {EFFORT_ENV: "low"}},
    "C2": {"batch": C2_BATCH},
    "C3": {"env": {PAIRS_MODEL_ENV: C3_MODEL}},
}
# F3.6: p90 nearest-rank, 90 % bootstrap band, 2000 resamples, seed 0; WIN needs >= 5 % of p90.
BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 0
WIN_MIN_FRACTION = 0.05
# F3.7 drift bands (advisory).
DRIFT_TOTAL_DROP = 0.20
DRIFT_LABEL_DROP = 2
DRIFT_REJECT_RISE = 3
CONFIRM_CANDIDATES = ("C1", "C2")
CONFIRM_MODEL = "gpt-5.5"
CONFIRM_HOST = "api.openai.com"
CONFIRM_TRIALS = 3
ORIGINAL_BATCH_MESSAGES = pc._batch_messages


def out_dir() -> Path:
    return Path(os.getenv("AI2_PERF_DIR") or Path.home() / ".ai2-perf")


def check_router() -> None:
    for env in ROUTER_ENVS:
        assert_router(os.getenv(env))
        print(f"provider {env} host={urlparse(os.getenv(env) or '').netloc}", file=sys.stderr)


def validate_c3_model(model: str) -> None:
    if model_name(model) == LABELER_MODEL or not classifier_family_ok(model):
        raise SystemExit(f"refusing C3 model {model!r}: labeler or not a classifier family")


@contextlib.contextmanager
def applied(candidate: str) -> Iterator[None]:
    """Apply one candidate's settings; restore env and PAIRS_PER_CALL whatever happens."""

    if candidate not in CANDIDATES:
        raise SystemExit(f"unknown candidate {candidate!r}")
    spec = CANDIDATES[candidate]
    env: Mapping[str, str] = spec.get("env", {})
    if PAIRS_MODEL_ENV in env:
        validate_c3_model(env[PAIRS_MODEL_ENV])
    saved_env = {key: os.environ.get(key) for key in env}
    saved_batch = pc.PAIRS_PER_CALL
    try:
        os.environ.update(env)
        if "batch" in spec:
            pc.PAIRS_PER_CALL = spec["batch"]
        yield
    finally:
        pc.PAIRS_PER_CALL = saved_batch
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextlib.contextmanager
def observe_batches(sizes: list[int]) -> Iterator[None]:
    """Record the size of every pairs batch built (one batch = one pairs request)."""

    lock = threading.Lock()

    def spy(pairs: Sequence[Any], offset: int) -> Any:
        built = ORIGINAL_BATCH_MESSAGES(pairs, offset)
        with lock:
            sizes.append(len(built[0]))
        return built

    pc._batch_messages = spy
    try:
        yield
    finally:
        pc._batch_messages = ORIGINAL_BATCH_MESSAGES


def check_batch(candidate: str, observed: int | None) -> None:
    """F12: a C2 trial whose requests did not carry 10 pairs measured nothing."""

    if candidate == "C2" and observed != C2_BATCH:
        raise SystemExit(f"C2 patch had no effect: pairs_per_call_observed={observed}, want 10")


class _TrialRuntime(ProcessingRuntime):
    """Keeps every pairs attempt's latency (llm_timing only aggregates)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pairs_latencies_ms: list[float] = []

    def _record_llm_attempt(
        self, operation: str, elapsed_ms: float, http_calls: int, trace: dict[str, Any] | None
    ) -> None:
        super()._record_llm_attempt(operation, elapsed_ms, http_calls, trace)
        if operation == "pairs":
            with self._state_lock:
                self.pairs_latencies_ms.append(round(elapsed_ms))


def run_job(request_file: str) -> dict[str, Any]:
    """One full job in-process (run_idp on the stored request, InMemorySnapshotStore)."""

    from app.pipeline import idp
    from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
    from app.security.service_envelope import verify_service_envelope
    from app.tools.store import InMemorySnapshotStore

    secret = os.getenv("AI2_SERVICE_HMAC_SECRET", "")
    if not secret:
        raise SystemExit("AI2_SERVICE_HMAC_SECRET is not set")
    raw = json.loads(Path(request_file).read_text(encoding="utf-8"))
    payload = rewrite_request(raw, "bakeoff", 0, secret=secret)
    envelope = verify_service_envelope(payload)
    request, adapted = adapt_be_ai2_processing_request(
        payload, tenant_id=envelope.tenant_id, actor_id=envelope.actor_id
    )
    limits = request.policy_flags.budget_limits
    runtime = _TrialRuntime(
        egress_allowed=True,
        use_vector=request.policy_flags.use_vector,
        max_processing_seconds=limits.max_processing_seconds,
        max_llm_calls=limits.max_llm_calls,
        max_embedding_tokens=limits.max_embedding_tokens,
    )
    sizes: list[int] = []
    with observe_batches(sizes):
        started = time.monotonic()
        result = idp.run_idp(
            adapted.record,
            adapted.envelope,
            llm=NineRouterClient(),
            store=InMemorySnapshotStore(),
            runtime=runtime,
        )
        wall_s = time.monotonic() - started
    coverage = (result.contribution.coverage if result.contribution else None) or {}
    pairs = (coverage.get("contract_graph") or {}).get("pairs") or {}
    return {
        "wall_s": round(wall_s, 3),
        "status": str(getattr(result.status, "value", result.status)),
        "calls": runtime.llm_calls_used,
        "llm_timing": coverage.get("llm_timing"),
        "pairs_latencies_ms": list(runtime.pairs_latencies_ms),
        "relations_total": pairs.get("relations_total"),
        "relations_by_label": pairs.get("relations_by_label"),
        "rejected": pairs.get("rejected"),
        "completion_tokens": pairs.get("completion_tokens"),
        "served_model": pairs.get("served_model"),
        "prompt_version": pairs.get("prompt_version"),
        "batches_completed": pairs.get("batches_completed"),
        "stopped_reason": pairs.get("stopped_reason"),
        "pairs_per_call_observed": max(sizes) if sizes else None,
    }


def trial(candidate: str, request_file: str, run: str) -> None:
    with applied(candidate):
        row = run_job(request_file)
    row = {"candidate": candidate, "run": run, "at": time.time(), **row}
    path = out_dir() / f"bakeoff-{run}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"calls={row.get('calls')} candidate={candidate} file={path}", file=sys.stderr)
    check_batch(candidate, row.get("pairs_per_call_observed"))
    print(row["wall_s"])


def load_rows(run: str) -> list[dict[str, Any]]:
    path = out_dir() / f"bakeoff-{run}.jsonl"
    if not path.exists():
        raise SystemExit(f"no trials recorded for run {run!r}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _p90(values: Sequence[float]) -> float:
    result = nearest_rank(values, 90)
    if result is None:
        raise SystemExit("no walls to rank")
    return result


def decide(incumbent: Sequence[float], candidate: Sequence[float]) -> dict[str, Any]:
    """F3.6 pre-registered rule on per-job walls (lower is better)."""

    p90_inc, p90_cand = _p90(incumbent), _p90(candidate)
    rng = random.Random(BOOTSTRAP_SEED)
    deltas = sorted(
        _p90(rng.choices(incumbent, k=len(incumbent)))
        - _p90(rng.choices(candidate, k=len(candidate)))
        for _ in range(BOOTSTRAP_ROUNDS)
    )
    ci_low, ci_high = nearest_rank(deltas, 5), nearest_rank(deltas, 95)
    delta = p90_inc - p90_cand
    if ci_low > 0 and delta >= WIN_MIN_FRACTION * p90_inc:
        verdict = "WIN"
    elif ci_high < 0:
        verdict = "KEEP"
    else:
        verdict = "TIE"
    return {
        "verdict": verdict,
        "p90_incumbent": p90_inc,
        "p90_candidate": p90_cand,
        "delta": round(delta, 3),
        "ci_low": round(ci_low, 3),
        "ci_high": round(ci_high, 3),
    }


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def _side_evidence(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    latencies = [ms for row in rows for ms in row.get("pairs_latencies_ms") or []]
    tokens = [row["completion_tokens"] for row in rows if row.get("completion_tokens") is not None]
    return {
        "pairs_calls": len(latencies),
        "pairs_latency_ms_median": _median(latencies),
        "completion_tokens_median": _median(tokens),
        "calls_per_job_median": _median([row["calls"] for row in rows if "calls" in row]),
    }


def rank(run: str, incumbent: str) -> None:
    rows = load_rows(run)
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_candidate.setdefault(row["candidate"], []).append(row)
    if incumbent not in by_candidate:
        raise SystemExit(f"incumbent {incumbent} has no trials in run {run!r}")
    inc_walls = [row["wall_s"] for row in by_candidate[incumbent]]
    print("| candidate | n | walls | p90 | side |\n|---|---|---|---|---|")
    for name, group in sorted(by_candidate.items()):
        walls = [row["wall_s"] for row in group]
        print(f"| {name} | {len(walls)} | {walls} | {_p90(walls)} | {_side_evidence(group)} |")
    verdicts = []
    for name, group in sorted(by_candidate.items()):
        if name == incumbent:
            continue
        result = decide(inc_walls, [row["wall_s"] for row in group])
        print(f"{name} vs {incumbent}: {json.dumps(result)}")
        verdicts.append((name, result))
    wins = [(name, r) for name, r in verdicts if r["verdict"] == "WIN"]
    if wins:
        best = max(wins, key=lambda item: item[1]["delta"])[0]
        print(f"verdict=WIN:{best}")
    elif verdicts and all(r["verdict"] == "KEEP" for _, r in verdicts):
        print(f"verdict=KEEP:{incumbent}")
    else:
        print("verdict=TIE")
    print("calls=0")


def _rejected(row: Mapping[str, Any]) -> int:
    rejected = row.get("rejected") or {}
    return int(rejected.get("ungrounded_span") or 0) + int(rejected.get("no_answer") or 0)


def drift(
    incumbent: Sequence[Mapping[str, Any]], candidate: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """F3.7 advisory bands on medians of the candidate against the incumbent."""

    def med(rows: Sequence[Mapping[str, Any]], pick: Callable[[Mapping[str, Any]], float]) -> float:
        return statistics.median(pick(row) for row in rows)

    flags = []
    inc_total = med(incumbent, lambda r: r.get("relations_total") or 0)
    cand_total = med(candidate, lambda r: r.get("relations_total") or 0)
    if inc_total and cand_total < (1 - DRIFT_TOTAL_DROP) * inc_total:
        flags.append(f"relations_total {inc_total}->{cand_total}")
    labels = sorted(
        {k for row in [*incumbent, *candidate] for k in (row.get("relations_by_label") or {})}
    )
    for label in labels:
        before = med(incumbent, lambda r: (r.get("relations_by_label") or {}).get(label, 0))
        after = med(candidate, lambda r: (r.get("relations_by_label") or {}).get(label, 0))
        if before - after >= DRIFT_LABEL_DROP:
            flags.append(f"label:{label} {before}->{after}")
    before, after = med(incumbent, _rejected), med(candidate, _rejected)
    if after - before >= DRIFT_REJECT_RISE:
        flags.append(f"rejected ungrounded_span+no_answer {before}->{after}")
    return {"flags": flags, "relations_total": [inc_total, cand_total]}


def _drift_cmd(run: str, candidate: str, incumbent: str) -> None:
    rows = load_rows(run)
    inc = [row for row in rows if row["candidate"] == incumbent]
    cand = [row for row in rows if row["candidate"] == candidate]
    if not inc or not cand:
        raise SystemExit("drift needs trials for both candidates")
    result = drift(inc, cand)
    print(json.dumps(result, ensure_ascii=False))
    print("drift=" + ("FLAG" if result["flags"] else "OK"))
    print("calls=0")


def gate_sha() -> str:
    """Digest of the code the seeded gate exercises; a reused gate result must match it."""

    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for base in (root / "app", root / "fixtures" / "seeded"):
        for path in sorted(base.rglob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


@contextlib.contextmanager
def count_http_calls(box: list[int]) -> Iterator[None]:
    """Sum HTTP requests over every NineRouterClient call (deduplicated by trace id)."""

    original = NineRouterClient.complete_json
    seen: set[str] = set()
    lock = threading.Lock()

    def counted(self: NineRouterClient, *args: Any, **kwargs: Any) -> Any:
        before = len(self.traces)
        try:
            return original(self, *args, **kwargs)
        finally:
            with lock:
                for trace in list(self.traces[before:]):
                    if trace.get("trace_id") not in seen:
                        seen.add(trace.get("trace_id"))
                        box[0] += int(trace.get("http_calls") or 0)

    NineRouterClient.complete_json = counted  # type: ignore[method-assign]
    try:
        yield
    finally:
        NineRouterClient.complete_json = original  # type: ignore[method-assign]


def run_gate(repeats: int = 3) -> int:
    from fixtures.seeded import run_live

    saved = sys.argv
    sys.argv = ["run_live", "--repeats", str(repeats)]
    try:
        return run_live.main()
    finally:
        sys.argv = saved


def gate(candidate: str) -> int:
    calls = [0]
    with applied(candidate), count_http_calls(calls):
        code = run_gate()
    print(f"gate candidate={candidate} exit={code} gate_sha={gate_sha()}")
    print(f"calls={calls[0]}")
    return code


def confirm_guard(candidate: str, permission: str | None, *, today: str | None = None) -> None:
    """D10: the only OpenAI path; every condition is checked before any request."""

    today = today or dt.date.today().isoformat()
    if candidate not in CONFIRM_CANDIDATES:
        raise SystemExit(f"confirm-openai is for production candidates {CONFIRM_CANDIDATES} only")
    if permission != today:
        raise SystemExit("confirm-openai needs --user-permission <today, YYYY-MM-DD>")
    if os.getenv("AI2_PERF_PROVIDER") != "openai":
        raise SystemExit("confirm-openai needs AI2_PERF_PROVIDER=openai")
    for env in ROUTER_ENVS:
        if urlparse(os.getenv(env) or "").netloc != CONFIRM_HOST:
            raise SystemExit(f"confirm-openai: {env} must point at {CONFIRM_HOST}")
    for env in (PAIRS_MODEL_ENV, "AI2_LLM_MODEL"):
        if model_name(os.getenv(env)) != CONFIRM_MODEL:
            raise SystemExit(f"confirm-openai: {env} must be {CONFIRM_MODEL}")


def _seeded_module(dossier: str) -> Any:
    from fixtures.seeded.score import DOSSIERS

    for modules in DOSSIERS.values():
        for module in modules:
            if module.DOSSIER_ID == dossier:
                return module
    raise SystemExit(f"unknown seeded dossier {dossier!r}")


def confirm_openai(candidate: str, dossier: str) -> int:
    """(a) 3+3 interleaved seeded trials C0/Cw, (b) run_live --repeats 1 for C0 and Cw."""

    from fixtures.seeded import funnel as seeded_funnel

    module = _seeded_module(dossier)
    walls: dict[str, list[float]] = {"C0": [], candidate: []}
    candidates_seen: set[int] = set()
    calls = [0]
    with count_http_calls(calls):
        for _ in range(CONFIRM_TRIALS):
            for name in ("C0", candidate):
                with applied(name):
                    started = time.monotonic()
                    result = seeded_funnel.run(
                        module.request(egress_allowed=True), llm=NineRouterClient()
                    )
                    walls[name].append(round(time.monotonic() - started, 3))
                candidates_seen.add(len(result.candidates))
        gates = {}
        for name in ("C0", candidate):
            with applied(name):
                gates[name] = run_gate(repeats=1)
    ok = (
        statistics.median(walls[candidate]) < statistics.median(walls["C0"])
        and max(walls[candidate]) < max(walls["C0"])
        and gates[candidate] == 0
    )
    print(json.dumps({"walls": walls, "candidates": sorted(candidates_seen), "gates": gates}))
    print(f"confirm={'PASS' if ok else 'FAIL'} candidate={candidate}")
    print(f"calls={calls[0]}")
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    trial_cmd = commands.add_parser("trial")
    trial_cmd.add_argument("--candidate", required=True)
    trial_cmd.add_argument("--request-file", required=True)
    trial_cmd.add_argument("--run", required=True)
    rank_cmd = commands.add_parser("rank")
    rank_cmd.add_argument("--run", required=True)
    rank_cmd.add_argument("--incumbent", default="C0")
    drift_cmd = commands.add_parser("drift")
    drift_cmd.add_argument("--run", required=True)
    drift_cmd.add_argument("--candidate", required=True)
    drift_cmd.add_argument("--incumbent", default="C0")
    gate_cmd = commands.add_parser("gate")
    gate_cmd.add_argument("--candidate", required=True)
    confirm_cmd = commands.add_parser("confirm-openai")
    confirm_cmd.add_argument("--candidate", required=True)
    confirm_cmd.add_argument("--user-permission", required=True)
    confirm_cmd.add_argument("--dossier", required=True)
    args = parser.parse_args(argv)
    if args.command == "confirm-openai":
        confirm_guard(args.candidate, args.user_permission)
        return confirm_openai(args.candidate, args.dossier)
    check_router()
    if args.command == "trial":
        trial(args.candidate, args.request_file, args.run)
    elif args.command == "rank":
        rank(args.run, args.incumbent)
    elif args.command == "drift":
        _drift_cmd(args.run, args.candidate, args.incumbent)
    else:
        return gate(args.candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
