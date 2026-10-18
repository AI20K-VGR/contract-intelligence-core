"""Record, measure and replay the pairs stage of one stored /jobs/idp request (P2).

Run inside the AI2 container; the local router (:20128) is the only accepted provider:

    python -m fixtures.perf.pairs_replay record --request-file F --runs 3 --label L
    python -m fixtures.perf.pairs_replay measure --request-file F
    python -m fixtures.perf.pairs_replay simulate --recordings '/root/.ai2-perf/pairs-rec-L-*.json'

``record`` sends the real batches (concurrency 5) and stores, per batch, the pair ids, the
answer, ``served_model`` and ``latency_ms``. ``simulate`` replays those answers offline with
injected failures for both failure policies (the D4 experiment). ``measure`` prints the pairs
wall time at the effective ``AI2_PAIRS_CONCURRENCY``; it is a diagnostic, not evidence that a
deployed knob works. Every file is written under ``$AI2_PERF_DIR`` (default ``~/.ai2-perf``),
never inside the repository; it holds contract text and must not be committed. Each command
prints ``calls=<HTTP requests sent>``.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import statistics
import sys
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.llm.client import NineRouterClient
from app.pipeline.contract_graph import pair_builder
from app.pipeline.contract_graph import pair_classifier as pc
from app.pipeline.contract_graph.pair_candidates import PairCandidate, PairSource
from app.pipeline.contract_graph.pair_classifier import ClassifierPair, classify_pairs
from app.pipeline.runtime import ProcessingRuntime, ProcessingTimeout
from fixtures.perf.replay_job import ROUTER_ENVS, assert_router, rewrite_request

KINDS = ("provider_error", "deadline", "served_model_rejected", "quota")
POLICIES = ("prefix", "keep_successful")
RECORD_CONCURRENCY = 5
# Replayed answers wait latency_ms * scale so completion order follows the recording.
REPLAY_TIME_SCALE = 0.002
_MAX_LLM_CALLS = 20
_MAX_SECONDS = 300


def out_dir() -> Path:
    return Path(os.getenv("AI2_PERF_DIR") or Path.home() / ".ai2-perf")


def check_router() -> None:
    for env in ROUTER_ENVS:
        assert_router(os.getenv(env))


def _ids(user: str) -> list[str]:
    return [row["id"] for row in json.loads(user)["pairs"]]


def batch_key(ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(ids))


def batch_index(ids: Sequence[str]) -> int:
    return (min(int(pid[1:]) for pid in ids) - 1) // pc.PAIRS_PER_CALL


def pairs_to_json(pairs: Sequence[ClassifierPair]) -> list[dict[str, Any]]:
    return [
        {
            "node_a": p.candidate.node_a,
            "node_b": p.candidate.node_b,
            "sources": sorted(s.value for s in p.candidate.sources),
            "score": p.candidate.score,
            "topic": p.candidate.topic,
            "referrer": p.candidate.referrer,
            "text_a": p.text_a,
            "text_b": p.text_b,
            "context_a": p.context_a,
            "context_b": p.context_b,
        }
        for p in pairs
    ]


def pairs_from_json(rows: Sequence[Mapping[str, Any]]) -> list[ClassifierPair]:
    return [
        ClassifierPair(
            PairCandidate(
                row["node_a"],
                row["node_b"],
                frozenset(PairSource(s) for s in row["sources"]),
                row["score"],
                row["topic"],
                row["referrer"],
            ),
            row["text_a"],
            row["text_b"],
            row["context_a"],
            row["context_b"],
        )
        for row in rows
    ]


class RecordingClient(NineRouterClient):
    """Real router client that keeps each batch's answer; shallow copies share the record."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.records: list[dict[str, Any]] = []
        self._records_lock = threading.Lock()

    def complete_json(self, system: str, user: str, **kwargs: Any) -> dict[str, Any]:
        data = super().complete_json(system, user, **kwargs)
        trace = self.traces[-1] if self.traces else {}
        with self._records_lock:
            self.records.append(
                {
                    "pair_ids": _ids(user),
                    "response": data,
                    "served_model": trace.get("served_model"),
                    "latency_ms": trace.get("latency_ms"),
                }
            )
        return data


class _QuotaError(Exception):
    status_code = 429
    body = {"error": {"code": "insufficient_quota"}}


class ReplayClient:
    """Answers a batch from its recording, matched by the set of pair ids."""

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        faults: Mapping[int, str] | None = None,
        time_scale: float = 0.0,
    ) -> None:
        self.records = {batch_key(r["pair_ids"]): r for r in records}
        self.faults = dict(faults or {})
        self.time_scale = time_scale
        self.calls: Counter[int] = Counter()
        self._lock = threading.Lock()
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return True

    def complete_json(self, system: str, user: str, **_kwargs: Any) -> dict[str, Any]:
        ids = _ids(user)
        record = self.records[batch_key(ids)]
        index = batch_index(ids)
        with self._lock:
            self.calls[index] += 1
        if self.time_scale:
            time.sleep((record.get("latency_ms") or 0) * self.time_scale / 1000)
        fault = self.faults.get(index)
        if fault == "provider_error":
            raise ValueError("replayed provider error")
        if fault == "quota":
            raise _QuotaError("replayed insufficient_quota")
        served = "unknown-model" if fault == "served_model_rejected" else record["served_model"]
        self.traces.append({"served_model": served, "latency_ms": record.get("latency_ms")})
        return record["response"]


class _DeadlineRuntime(ProcessingRuntime):
    deadline_batch: int | None = None

    def complete_json(self, client: Any, system: str, user: str, **kwargs: Any) -> Any:
        if self.deadline_batch is not None and batch_index(_ids(user)) == self.deadline_batch:
            raise ProcessingTimeout("replayed deadline")
        return super().complete_json(client, system, user, **kwargs)


def run_offline(
    pairs: Sequence[ClassifierPair],
    records: Sequence[Mapping[str, Any]],
    *,
    k: int | None = None,
    kind: str | None = None,
    policy: str = "prefix",
    time_scale: float = REPLAY_TIME_SCALE,
) -> dict[str, Any]:
    faults = {} if k is None or kind == "deadline" else {k: kind}
    client = ReplayClient(records, faults=faults, time_scale=time_scale)
    runtime = _DeadlineRuntime(
        egress_allowed=True,
        max_llm_calls=_MAX_LLM_CALLS,
        max_processing_seconds=_MAX_SECONDS,
        sleep=lambda _s: None,
    )
    runtime.deadline_batch = k if kind == "deadline" else None
    outcome = classify_pairs(
        pairs,
        client=client,
        runtime=runtime,
        concurrency=RECORD_CONCURRENCY,
        failure_policy=policy,
    )
    # One injected fault and every other batch answers, so batches 0..k-1 are accepted under
    # both policies and anything completed beyond k was accepted after the failed batch.
    accepted_after = None if k is None else max(0, outcome.batches_completed - k)
    wasted = 0
    if policy == "prefix" and outcome.stopped_reason is not None and k is not None:
        failed_at = outcome.batches_completed
        wasted = sum(n for index, n in client.calls.items() if index > failed_at)
    return {
        "http_calls_spent": runtime.llm_calls_used,
        "calls_wasted": wasted,
        "relations_total": len(outcome.decisions),
        "relations_by_label": dict(Counter(d.label.value for d in outcome.decisions)),
        "pairs_unclassified": outcome.stats["pairs_unclassified"],
        "batches_completed": outcome.batches_completed,
        "accepted_after_rejected": accepted_after or 0,
        "stopped_reason": outcome.stopped_reason,
        "reason_code": f"PARTIAL_{outcome.stopped_reason}" if outcome.stopped_reason else None,
        "pair_relations_ran": outcome.batches_completed >= 1,
        "limited_coverage_issue": False,  # llm mode never emits LIMITED_COVERAGE
        # "PARTIAL_* = everything after the stop is unclassified" holds iff nothing past k ran.
        "partial_means_rest_unclassified": None if accepted_after is None else accepted_after == 0,
        "issues": [code for code, _ in runtime.issues],
    }


def _median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else 0


def simulate(recordings: Sequence[Mapping[str, Any]], *, time_scale: float = 0.0) -> list[dict]:
    """Failure matrix (k x kind x policy, plus a no-failure run), medians over recordings."""

    if not recordings:
        raise ValueError("no recordings")
    loaded = [(pairs_from_json(r["pairs"]), r["batches"]) for r in recordings]
    n_batches = max(len(batches) for _, batches in loaded)
    cases: list[tuple[int | None, str | None, str]] = [(None, None, p) for p in POLICIES]
    cases += [(k, kind, p) for k in range(n_batches) for kind in KINDS for p in POLICIES]
    base = [run_offline(pairs, b, time_scale=time_scale) for pairs, b in loaded]
    rows = []
    for k, kind, policy in cases:
        runs = [
            run_offline(pairs, b, k=k, kind=kind, policy=policy, time_scale=time_scale)
            for pairs, b in loaded
        ]
        labels = sorted({label for r in runs for label in r["relations_by_label"]})
        row: dict[str, Any] = {"k": k, "kind": kind, "policy": policy, "runs": len(runs)}
        for key in (
            "calls_wasted",
            "http_calls_spent",
            "relations_total",
            "pairs_unclassified",
            "batches_completed",
            "accepted_after_rejected",
        ):
            row[key] = _median([r[key] for r in runs])
        row["relations_delta"] = _median(
            [r["relations_total"] - b["relations_total"] for r, b in zip(runs, base, strict=True)]
        )
        row["relations_by_label"] = {
            label: _median([r["relations_by_label"].get(label, 0) for r in runs])
            for label in labels
        }
        for key in (
            "stopped_reason",
            "reason_code",
            "pair_relations_ran",
            "limited_coverage_issue",
            "partial_means_rest_unclassified",
        ):
            row[key] = Counter(r[key] for r in runs).most_common(1)[0][0]
        row["issues"] = sorted({code for r in runs for code in r["issues"]})
        rows.append(row)
    return rows


def render_simulation(rows: Sequence[Mapping[str, Any]]) -> str:
    cols = (
        "k",
        "kind",
        "policy",
        "calls_wasted",
        "http_calls_spent",
        "relations_total",
        "relations_delta",
        "pairs_unclassified",
        "batches_completed",
        "accepted_after_rejected",
        "stopped_reason",
        "reason_code",
        "pair_relations_ran",
        "partial_means_rest_unclassified",
        "relations_by_label",
    )
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c)) for c in cols) + " |")
    return "\n".join(lines)


def _pairs_client() -> NineRouterClient:
    client = pair_builder.classifier_client(
        NineRouterClient(), os.getenv(pair_builder.PAIRS_MODEL_ENV)
    )
    if client is None:
        raise SystemExit("refusing to run: pairs client is not configured")
    assert_router(client.base_url)
    return client


def capture_pairs(request_file: str) -> tuple[list[ClassifierPair], int]:
    """The classifier pairs of a stored request; cached outside the repo by request digest."""

    raw = Path(request_file).read_bytes()
    cache = out_dir() / f"pairs-cache-{hashlib.sha256(raw).hexdigest()[:16]}.json"
    if cache.exists():
        return pairs_from_json(json.loads(cache.read_text(encoding="utf-8"))), 0

    from app.pipeline import idp
    from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
    from app.security.service_envelope import verify_service_envelope
    from app.tools.store import InMemorySnapshotStore

    class _Captured(BaseException):
        pass

    secret = os.getenv("AI2_SERVICE_HMAC_SECRET", "")
    if not secret:
        raise SystemExit("AI2_SERVICE_HMAC_SECRET is not set")
    payload = rewrite_request(json.loads(raw), "pairs-replay", 0, secret=secret)
    envelope = verify_service_envelope(payload)
    request, adapted = adapt_be_ai2_processing_request(
        payload, tenant_id=envelope.tenant_id, actor_id=envelope.actor_id
    )
    box: dict[str, list[ClassifierPair]] = {}
    original = pair_builder.classify_pairs

    def spy(pairs: Sequence[ClassifierPair], **_kwargs: Any) -> Any:
        box["pairs"] = list(pairs)
        raise _Captured

    limits = request.policy_flags.budget_limits
    runtime = ProcessingRuntime(
        egress_allowed=True,
        max_processing_seconds=limits.max_processing_seconds,
        max_llm_calls=limits.max_llm_calls,
    )
    pair_builder.classify_pairs = spy
    try:
        idp.run_idp(
            adapted.record,
            adapted.envelope,
            llm=NineRouterClient(),
            store=InMemorySnapshotStore(),
            runtime=runtime,
        )
    except _Captured:
        pass
    finally:
        pair_builder.classify_pairs = original
    if "pairs" not in box:
        raise SystemExit("the request never reached the pairs classifier")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pairs_to_json(box["pairs"]), ensure_ascii=False), encoding="utf-8")
    return box["pairs"], runtime.llm_calls_used


def _runtime() -> ProcessingRuntime:
    return ProcessingRuntime(
        egress_allowed=True, max_llm_calls=_MAX_LLM_CALLS, max_processing_seconds=_MAX_SECONDS
    )


def record(request_file: str, runs: int, label: str) -> None:
    pairs, calls = capture_pairs(request_file)
    base = _pairs_client()
    for index in range(runs):
        client = RecordingClient(base_url=base.base_url, api_key=base.api_key, model=base.model)
        runtime = _runtime()
        started = time.perf_counter()
        outcome = classify_pairs(
            pairs, client=client, runtime=runtime, concurrency=RECORD_CONCURRENCY
        )
        wall_ms = round((time.perf_counter() - started) * 1000)
        calls += runtime.llm_calls_used
        path = out_dir() / f"pairs-rec-{label}-{index}.json"
        path.write_text(
            json.dumps(
                {
                    "label": label,
                    "index": index,
                    "pairs": pairs_to_json(pairs),
                    "batches": sorted(client.records, key=lambda r: batch_index(r["pair_ids"])),
                    "outcome": {
                        "wall_ms": wall_ms,
                        "batches_completed": outcome.batches_completed,
                        "stopped_reason": outcome.stopped_reason,
                        "relations_total": len(outcome.decisions),
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(
            f"run={index} file={path} wall_ms={wall_ms} batches_completed="
            f"{outcome.batches_completed} stopped_reason={outcome.stopped_reason}",
            flush=True,
        )
    print(f"calls={calls}")


def measure(request_file: str) -> None:
    pairs, calls = capture_pairs(request_file)
    runtime = _runtime()
    concurrency = pc._pairs_concurrency()
    started = time.perf_counter()
    outcome = classify_pairs(pairs, client=_pairs_client(), runtime=runtime)
    wall_ms = round((time.perf_counter() - started) * 1000)
    timing = (runtime.llm_timing() or {}).get("by_operation", {}).get("pairs", {})
    print(
        f"concurrency={concurrency} pairs_wall_ms={wall_ms} llm_ms_max={timing.get('llm_ms_max')} "
        f"batches_completed={outcome.batches_completed} stopped_reason={outcome.stopped_reason}"
    )
    print(f"calls={calls + runtime.llm_calls_used}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    record_cmd = commands.add_parser("record")
    record_cmd.add_argument("--request-file", required=True)
    record_cmd.add_argument("--runs", type=int, default=3)
    record_cmd.add_argument("--label", required=True)
    measure_cmd = commands.add_parser("measure")
    measure_cmd.add_argument("--request-file", required=True)
    simulate_cmd = commands.add_parser("simulate")
    simulate_cmd.add_argument("--recordings", required=True)
    args = parser.parse_args(argv)
    check_router()
    out_dir().mkdir(parents=True, exist_ok=True)
    if args.command == "record":
        if args.runs < 1:
            parser.error("--runs must be >= 1")
        record(args.request_file, args.runs, args.label)
    elif args.command == "measure":
        measure(args.request_file)
    else:
        paths = sorted(glob.glob(args.recordings))
        recordings = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
        rows = simulate(recordings, time_scale=REPLAY_TIME_SCALE)
        print(f"recordings={len(paths)}")
        print(render_simulation(rows))
        print("json=" + json.dumps(rows, ensure_ascii=False))
        print("calls=0")


if __name__ == "__main__":
    main(sys.argv[1:])
