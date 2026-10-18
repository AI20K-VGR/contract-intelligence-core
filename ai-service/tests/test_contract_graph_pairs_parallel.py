"""P2: parallel pair batches keep the sequential outcome within INV-1/INV-2; KD2/KD3/KD6 pinned."""

from __future__ import annotations

import inspect
import json
import logging
import math
import re
import threading
import time
from collections import Counter
from typing import Any

import httpx
import openai
import pytest

from app.pipeline.contract_graph import pair_builder
from app.pipeline.contract_graph import pair_classifier as pc
from app.pipeline.contract_graph.pair_candidates import PairCandidate, PairSource
from app.pipeline.contract_graph.pair_classifier import ClassifierPair, classify_pairs
from app.pipeline.runtime import ProcessingRuntime, ProcessingTimeout
from fixtures.contract_graph_records import Spec, dossier

JOIN = 5.0
TEXT_A = "Bên Mua thanh toán trong 30 ngày kể từ ngày nhận hóa đơn."
TEXT_B = "Bên Mua thanh toán trong 15 ngày kể từ ngày nhận hóa đơn."
REFERRER = "Bên B lập báo cáo sự cố theo khoản 2 Điều 3 của Hợp đồng trong vòng 24 giờ."
TARGET = "3.2. Bên B phải khắc phục sự cố trong vòng 04 giờ kể từ khi nhận thông báo."
_REQ = httpx.Request("POST", "http://router.test/v1/chat/completions")
# Per OK batch: ungrounded + abstain + missing id stay unclassified.
UNCLASSIFIED_PER_OK_BATCH = 3


def make_pairs(n: int = 40) -> list[ClassifierPair]:
    pairs = []
    for i in range(n):
        if i % 8 == 7:
            candidate = PairCandidate(
                f"b{i}", f"a{i}", frozenset({PairSource.EXPLICIT_REF}), 4, None, referrer=f"a{i}"
            )
            pairs.append(ClassifierPair(candidate, TARGET, REFERRER, "Điều 3", "Điều 6"))
        else:
            candidate = PairCandidate(f"a{i}", f"b{i}", frozenset({PairSource.SAME_KEY}), 2, "P")
            pairs.append(ClassifierPair(candidate, TEXT_A, TEXT_B, "Điều 3", "Điều 4"))
    return pairs


def batch_of(user: str) -> int:
    ids = [p["id"] for p in json.loads(user)["pairs"]]
    return (int(ids[0][1:]) - 1) // pc.PAIRS_PER_CALL


def candidate_batch(node_id: str) -> int:
    return int(re.sub(r"\D", "", node_id)) // pc.PAIRS_PER_CALL


def response_for(user: str) -> dict[str, Any]:
    """Every post-processing branch: accepted, unrelated, ungrounded, abstain, missing id,
    duplicate id, unknown id and the explicit-reference fallback."""

    ids = [p["id"] for p in json.loads(user)["pairs"]]
    conflict = {"label": "CONFLICT", "span_a": TEXT_A, "span_b": TEXT_B}
    rows: list[dict[str, Any]] = []
    for n, pid in enumerate(ids):
        if n in (0, 5):
            rows.append({"id": pid, **conflict})
        elif n in (1, 6, 7):
            rows.append({"id": pid, "label": "UNRELATED"})
        elif n == 2:
            rows.append({"id": pid, **conflict, "span_a": "invented text not in clause"})
        elif n == 3:
            rows.append({"id": pid, "label": "ABSTAIN"})
    if len(ids) > 5:
        rows.append({"id": ids[5], **conflict})
    rows.append({"id": "zz", **conflict})
    return {"results": rows}


class QuotaError(Exception):
    status_code = 429
    body = {"error": {"code": "insufficient_quota"}}


def unavailable() -> openai.InternalServerError:
    return openai.InternalServerError(
        "overloaded", response=httpx.Response(503, request=_REQ), body=None
    )


def rate_limited() -> openai.RateLimitError:
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=_REQ), body=None)


class Script:
    """State shared by every shallow copy of the fake client."""

    def __init__(self, plan=None, *, reverse=False, n_batches=5, delay=0.0, actions=None):
        self.plan = dict(plan or {})
        self.actions = dict(actions or {})  # (batch, attempt) -> "unavailable" | "quota" | ...
        self.reverse = reverse
        self.delay = delay
        self.lock = threading.Lock()
        self.prompts: list[str] = []
        self.attempts: Counter[int] = Counter()
        self.done = [threading.Event() for _ in range(max(n_batches, 1) + 1)]
        self.events: dict[str, threading.Event] = {}
        self.on_call = None

    def event(self, name: str) -> threading.Event:
        with self.lock:
            return self.events.setdefault(name, threading.Event())


class FakeClient:
    def __init__(self, script: Script):
        self.script = script
        self.traces: list[dict[str, Any]] = []

    def configured(self) -> bool:
        return True

    def complete_json(self, system: str, user: str, **_kw: Any) -> dict[str, Any]:
        s, b = self.script, batch_of(user)
        with s.lock:
            s.prompts.append(user)
            s.attempts[b] += 1
            attempt = s.attempts[b]
        try:
            if s.on_call is not None:
                s.on_call(b)
            if s.reverse and b + 1 < len(s.done) - 1:
                s.done[b + 1].wait(JOIN)
            if s.delay:
                time.sleep(s.delay)
            action = s.actions.get((b, attempt)) or s.plan.get(b)
            if action == "provider":
                raise ValueError("provider rejected the request")
            if action == "quota":
                # The lower batches are already in flight when the quota flips (INV-2 scope).
                limit = time.monotonic() + JOIN
                while time.monotonic() < limit and any(s.attempts[j] == 0 for j in range(b)):
                    time.sleep(0.005)
                s.event(f"quota-{b}").set()
                raise QuotaError("quota")
            if action == "unavailable":
                raise unavailable()
            if action == "rate_limited":
                raise rate_limited()
            served = "unknown-model" if action == "served" else f"claude-b{b}"
            self.traces.append(
                {
                    "served_model": served,
                    "prompt_tokens": 10 + b,
                    "completion_tokens": 1 + b,
                    "latency_ms": 100 + b,
                }
            )
            return response_for(user)
        finally:
            s.done[b].set()


class ScriptRuntime(ProcessingRuntime):
    """Throws ``ProcessingTimeout`` for scripted batches, like a deadline hit mid-batch."""

    script: Any = None

    def complete_json(self, client, system, user, **kw):
        s, b = self.script, batch_of(user)
        if s is not None and s.plan.get(b) == "deadline":
            with s.lock:
                s.prompts.append(user)
                s.attempts[b] += 1
            try:
                if s.reverse and b + 1 < len(s.done) - 1:
                    s.done[b + 1].wait(JOIN)
            finally:
                s.done[b].set()
            raise ProcessingTimeout("scripted deadline")
        return super().complete_json(client, system, user, **kw)


def make_runtime(script: Script | None = None, **kw: Any) -> ScriptRuntime:
    kw.setdefault("egress_allowed", True)
    kw.setdefault("max_llm_calls", 50)
    kw.setdefault("max_processing_seconds", 1000)
    kw.setdefault("max_attempts", 3)
    kw.setdefault("call_timeout_seconds", 45)
    kw.setdefault("sleep", lambda _s: None)
    kw.setdefault("jitter", lambda: 0.0)
    runtime = ScriptRuntime(**kw)
    runtime.script = script
    return runtime


def observe(conc, plan=None, *, reverse=False, n=40, script=None, runtime_kw=None, **kwargs):
    n_batches = math.ceil(n / pc.PAIRS_PER_CALL)
    script = script or Script(plan, reverse=reverse, n_batches=n_batches)
    client = FakeClient(script)
    runtime = make_runtime(script, **(runtime_kw or {}))
    events: list[dict[str, Any]] = []
    outcome = classify_pairs(
        make_pairs(n),
        client=client,
        runtime=runtime,
        event_sink=events.append,
        requested_model="claude-req",
        request_id="req-1",
        concurrency=conc,
        **kwargs,
    )
    return {
        "decisions": outcome.decisions,
        "events": events,
        "stats": outcome.stats,
        "stopped_reason": outcome.stopped_reason,
        "batches_completed": outcome.batches_completed,
        "issues": list(runtime.issues),
        "fallback_count": runtime.fallback_count,
        "traces": list(client.traces),
        "llm_calls_used": runtime.llm_calls_used,
    }, script


SPEND_STATS = ("llm_calls", "prompt_tokens", "completion_tokens")


def assert_equal_except_spend(par: dict, seq: dict) -> None:
    for key in ("decisions", "events", "stopped_reason", "batches_completed", "issues"):
        assert par[key] == seq[key], key
    assert par["fallback_count"] == seq["fallback_count"]
    assert {k: v for k, v in par["stats"].items() if k not in SPEND_STATS} == {
        k: v for k, v in seq["stats"].items() if k not in SPEND_STATS
    }
    for key in SPEND_STATS:
        assert par["stats"][key] >= seq["stats"][key], key
    assert par["llm_calls_used"] >= seq["llm_calls_used"]
    # Discarded batches' traces are spend (KD1); the consumed prefix is identical.
    assert par["traces"][: len(seq["traces"])] == seq["traces"]


# R2.1 — INV-1
def test_parallel_equals_sequential_happy_path_reverse_completion():
    seq, _ = observe(1)
    par, script = observe(5, reverse=True)
    assert par == seq
    assert seq["batches_completed"] == 5 and seq["stopped_reason"] is None
    outcomes = Counter(e["outcome"] for e in seq["events"] if e["phase"] == "classifier")
    assert outcomes["accepted"] == 15 and outcomes["validator_reject"] == 5
    assert any(e.get("reason") == "explicit_reference" for e in seq["events"])
    assert {e["outcome"] for e in seq["events"] if e["phase"] == "batch"} == {
        "unknown_id",
        "duplicate_id",
    }
    assert seq["stats"]["pairs_unclassified"] == 5 * UNCLASSIFIED_PER_OK_BATCH


# R2.2 — INV-2
@pytest.mark.parametrize("kind", ["provider", "deadline", "served", "quota"])
@pytest.mark.parametrize("k", [0, 2, 4])
def test_parallel_equals_sequential_with_failure(k, kind):
    seq, _ = observe(1, {k: kind})
    par, script = observe(5, {k: kind}, reverse=True)
    assert seq["batches_completed"] == k and seq["stopped_reason"] is not None
    assert_equal_except_spend(par, seq)


# R2.3 — INV-3
def test_no_runtime_mutation_after_return():
    script = Script({0: "provider"}, delay=0.0)

    def slow_later_batches(b: int) -> None:
        if b > 0:
            time.sleep(0.2)

    script.on_call = slow_later_batches
    client, runtime = FakeClient(script), make_runtime(script)
    outcome = classify_pairs(make_pairs(), client=client, runtime=runtime, concurrency=5)
    assert outcome.stopped_reason == "LLM_FALLBACK"
    assert not [t for t in threading.enumerate() if t.name.startswith("ai2-pairs")]
    used, issues, fallbacks = runtime.llm_calls_used, list(runtime.issues), runtime.fallback_count
    time.sleep(0.4)
    assert runtime.llm_calls_used == used
    assert runtime.issues == issues and runtime.fallback_count == fallbacks


# R2.4 — INV-4
def test_served_model_attributed_per_batch():
    par, _ = observe(5, reverse=True)
    for decision in par["decisions"]:
        expected = f"claude-b{candidate_batch(decision.candidate.node_a)}"
        assert decision.served_model == expected
    for event in par["events"]:
        if event["phase"] == "classifier":
            assert event["served_model"] == f"claude-b{candidate_batch(event['node_a_id'])}"
    assert par["stats"]["served_model"] == "claude-b4"


def test_missing_current_trace_cannot_borrow_another_batch_trace():
    # Parallel counterpart of test_missing_current_trace_cannot_reuse_prior_claude_trace.
    script = Script(reverse=True)

    class NoTraceForBatch1(FakeClient):
        def complete_json(self, system, user, **kw):
            result = super().complete_json(system, user, **kw)
            if batch_of(user) == 1:
                self.traces.clear()
            return result

    runtime = make_runtime(script)
    outcome = classify_pairs(
        make_pairs(), client=NoTraceForBatch1(script), runtime=runtime, concurrency=5
    )
    assert outcome.batches_completed == 1
    assert outcome.stopped_reason == "LLM_FALLBACK"


# R2.5 — INV-5 (no assertion on which batch loses: KD2)
def test_budget_cap_holds_under_parallel_retries():
    actions = {(b, 1): "unavailable" for b in range(5)}
    script = Script(actions=actions)
    par, _ = observe(5, script=script, runtime_kw={"max_llm_calls": 7})
    assert par["llm_calls_used"] <= 7
    assert par["stopped_reason"] == "LLM_FALLBACK"
    assert {code for code, _ in par["issues"]} <= {"LLM_BUDGET_EXCEEDED", "LLM_UNAVAILABLE"}
    seq, _ = observe(1, script=Script(actions=actions), runtime_kw={"max_llm_calls": 7})
    kept = par["batches_completed"]
    assert par["decisions"] == tuple(
        d for d in seq["decisions"] if candidate_batch(d.candidate.node_a) < kept
    )


# R2.6
def test_failure_blocks_only_later_batches(monkeypatch):
    marked = threading.Event()
    original = pc._AbortGate.mark

    def mark(self, index):
        original(self, index)
        marked.set()

    monkeypatch.setattr(pc._AbortGate, "mark", mark)
    actions = {(0, 1): "unavailable", (3, 1): "unavailable", (4, 1): "unavailable"}
    script = Script({2: "provider"}, actions=actions)
    runtime_kw = {"sleep": lambda _s: marked.wait(JOIN)}
    par, script = observe(5, script=script, runtime_kw=runtime_kw)
    assert script.attempts[0] == 2  # batch 0 retried after the failure and was kept
    assert script.attempts[1] == 1
    # Batches after the failure never retry (a first attempt may already be blocked too).
    assert script.attempts[3] <= 1 and script.attempts[4] <= 1
    assert par["batches_completed"] == 2 and par["stopped_reason"] == "LLM_FALLBACK"
    assert [code for code, _ in par["issues"]] == ["LLM_NON_RETRYABLE"]


# R2.7
def test_parallel_wall_time_beats_sequential():
    started = time.perf_counter()
    observe(5, script=Script(delay=0.3))
    parallel = time.perf_counter() - started
    started = time.perf_counter()
    observe(1, script=Script(delay=0.3))
    sequential = time.perf_counter() - started
    assert parallel < 0.9
    assert sequential >= 1.5


class _ExecutorSpy:
    created: list[int] = []

    def __init__(self, *args, max_workers=None, thread_name_prefix="", **kwargs):
        from concurrent.futures import ThreadPoolExecutor

        _ExecutorSpy.created.append(max_workers)
        assert thread_name_prefix == "ai2-pairs"
        self._inner = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai2-pairs")

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._inner.shutdown(wait=True)
        return False


class _NoExecutor:
    def __init__(self, *args, **kwargs):
        raise AssertionError("no executor may be created on the sequential path")


# R2.8
@pytest.mark.parametrize(
    ("raw", "expected", "warns"),
    [
        (None, 5, False),
        ("1", 1, False),
        ("3", 3, False),
        (" 2 ", 2, False),
        ("abc", 5, True),
        ("0", 5, True),
        ("-2", 5, True),
        ("2.5", 5, True),
    ],
)
def test_concurrency_env_parsing_and_sequential_fallback(monkeypatch, caplog, raw, expected, warns):
    if raw is None:
        monkeypatch.delenv(pc.PAIRS_CONCURRENCY_ENV, raising=False)
    else:
        monkeypatch.setenv(pc.PAIRS_CONCURRENCY_ENV, raw)
    with caplog.at_level(logging.WARNING):
        assert pc._pairs_concurrency() == expected
    assert ("AI2_PAIRS_CONCURRENCY" in caplog.text) is warns


def test_env_one_takes_sequential_path_and_default_sizes_the_pool(monkeypatch):
    monkeypatch.setenv(pc.PAIRS_CONCURRENCY_ENV, "1")
    monkeypatch.setattr(pc, "ThreadPoolExecutor", _NoExecutor)
    seq, _ = observe(None)
    monkeypatch.delenv(pc.PAIRS_CONCURRENCY_ENV)
    monkeypatch.setattr(pc, "ThreadPoolExecutor", _ExecutorSpy)
    _ExecutorSpy.created = []
    par, _ = observe(None)
    observe(None, n=10)
    assert _ExecutorSpy.created == [5, 2]
    assert par == seq


def test_explicit_concurrency_must_be_positive():
    with pytest.raises(ValueError):
        observe(0)


# R2.9
def test_progress_reported_in_order_from_coordinator():
    def run(conc):
        seen: list[tuple[int, str]] = []
        runtime_kw = {
            "on_progress": lambda p: seen.append((p["done"], threading.current_thread().name))
        }
        observe(conc, n=43, runtime_kw=runtime_kw)
        return seen

    seq, par = run(1), run(5)
    assert [done for done, _ in par] == [0, 8, 16, 24, 32, 40] == [done for done, _ in seq]
    assert {name for _, name in par} == {threading.current_thread().name}


# R2.10
def test_keep_successful_experiment_semantics():
    par, _ = observe(5, {2: "provider"}, reverse=True, failure_policy="keep_successful")
    kept = {candidate_batch(d.candidate.node_a) for d in par["decisions"]}
    assert kept == {0, 1, 3, 4}
    assert par["batches_completed"] == 4
    assert par["stopped_reason"] == "LLM_FALLBACK"
    batch2 = [e for e in par["events"] if e["phase"] == "classifier" and e["batch_id"] == "batch-3"]
    assert {(e["outcome"], e["reason"]) for e in batch2} == {("no_answer", "LLM_FALLBACK")}
    assert not [e for e in par["events"] if e.get("outcome") == "not_sent"]
    assert par["stats"]["pairs_unclassified"] == 4 * UNCLASSIFIED_PER_OK_BATCH + 8
    assert [code for code, _ in par["issues"]] == ["LLM_NON_RETRYABLE"]


def test_keep_successful_requires_parallel_and_known_policy():
    with pytest.raises(ValueError):
        observe(1, failure_policy="keep_successful")
    with pytest.raises(ValueError):
        observe(5, failure_policy="best_effort")


def test_build_pair_relations_uses_default_policy(monkeypatch):
    assert "failure_policy" not in inspect.getsource(pair_builder)
    seen: dict[str, Any] = {}

    def spy(pairs, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop after capture")

    monkeypatch.setattr(pair_builder, "classify_pairs", spy)
    for key in (pair_builder.PAIRS_BASE_URL_ENV, pair_builder.PAIRS_API_KEY_ENV):
        monkeypatch.delenv(key, raising=False)
    record = dossier(
        [
            (
                "f",
                "body",
                [
                    Spec("d3", "Điều 3", "Thanh toán"),
                    Spec("a", "1.", TEXT_A, "d3"),
                    Spec("b", "2.", TEXT_B, "d3"),
                ],
            )
        ],
        [],
    )
    record.content_sharing_consent = True
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=10, max_processing_seconds=1000)
    with pytest.raises(RuntimeError, match="stop after capture"):
        pair_builder.build_pair_relations(
            record, [], llm=FakeClient(Script()), runtime=runtime, model="claude-test"
        )
    assert seen and "failure_policy" not in seen and "concurrency" not in seen


# R2.11
@pytest.mark.parametrize("n", [0, 1, 8, 9, 40, 43])
@pytest.mark.parametrize("used0", [0, 2])
@pytest.mark.parametrize("max_llm", [0, 1, 3, 100])
@pytest.mark.parametrize("max_calls", [0, 2, 5])
@pytest.mark.parametrize("deadline_ok", [True, False])
def test_plan_batches_matches_sequential_predicate(n, used0, max_llm, max_calls, deadline_ok):
    runtime = make_runtime(
        Script(), max_llm_calls=max_llm, max_processing_seconds=1000 if deadline_ok else 100
    )
    runtime.llm_calls_used = used0
    outcome = classify_pairs(
        make_pairs(n),
        client=FakeClient(Script()),
        runtime=runtime,
        max_calls=max_calls,
        concurrency=1,
    )
    n_batches = math.ceil(n / pc.PAIRS_PER_CALL)
    assert pc._plan_batches(n_batches, used0, max_llm, max_calls, deadline_ok) == (
        outcome.batches_completed,
        outcome.stopped_reason,
    )


def test_plan_batches_checks_deadline_only_at_submit():
    assert pc._plan_batches(5, 0, 100, 5, True) == (5, None)
    assert pc._plan_batches(5, 0, 100, 5, False) == (0, "DEADLINE")
    assert pc._plan_batches(5, 0, 3, 5, False) == (0, "DEADLINE")
    assert pc._plan_batches(5, 3, 3, 5, False) == (0, "BUDGET_EXHAUSTED")


def test_batch_size_is_read_at_call_time(monkeypatch):
    monkeypatch.setattr(pc, "PAIRS_PER_CALL", 10)
    script = Script()
    client, runtime = FakeClient(script), make_runtime(script)
    outcome = classify_pairs(make_pairs(40), client=client, runtime=runtime, concurrency=5)
    assert sorted(len(json.loads(p)["pairs"]) for p in script.prompts) == [10] * 4
    assert outcome.batches_completed == 4


# R2.12
def test_llm_call_log_lines_attribute_each_batch(caplog):
    with caplog.at_level(logging.INFO, logger="app.pipeline.runtime"):
        observe(5, reverse=True)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("ai2.llm_call ")]
    pairs = {
        (re.search(r"served_model=(\S+)", line)[1], re.search(r"latency_ms=(\S+)", line)[1])
        for line in lines
    }
    assert len(lines) == 5
    assert pairs == {(f"claude-b{b}", str(100 + b)) for b in range(5)}


# R2.13
def test_pairs_replay_guard_and_replay_matching(monkeypatch, capsys):
    from fixtures.perf import pairs_replay

    monkeypatch.setenv("AI2_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_BASE_URL", "https://api.openai.com/v1")
    for argv in (
        ["record", "--request-file", "x.json", "--runs", "1", "--label", "t"],
        ["measure", "--request-file", "x.json"],
    ):
        with pytest.raises(SystemExit, match="local router"):
            pairs_replay.main(argv)

    pairs = make_pairs(40)
    users = [
        json.dumps({"pairs": [{"id": f"p{o + n + 1}"} for n in range(8)]}) for o in range(0, 40, 8)
    ]
    records = [
        {
            "pair_ids": [p["id"] for p in json.loads(u)["pairs"]][::-1],
            "response": response_for(u),
            "served_model": "gpt-5.6-luna",
            "latency_ms": 1000 + i,
        }
        for i, u in enumerate(users)
    ]
    recording = {"pairs": pairs_replay.pairs_to_json(pairs), "batches": records}
    assert pairs_replay.pairs_from_json(recording["pairs"]) == pairs
    replay = pairs_replay.ReplayClient(records)
    assert replay.complete_json("s", users[2]) == records[2]["response"]
    assert replay.traces[-1]["served_model"] == "gpt-5.6-luna"
    with pytest.raises(KeyError):
        replay.complete_json("s", json.dumps({"pairs": [{"id": "p99"}]}))

    rows = pairs_replay.simulate([recording, recording])
    by_case = {(r["k"], r["kind"], r["policy"]): r for r in rows}
    base = by_case[(None, None, "prefix")]
    assert base["batches_completed"] == 5 and base["stopped_reason"] is None
    assert base["calls_wasted"] == 0 and base["http_calls_spent"] == 5
    prefix = by_case[(2, "provider_error", "prefix")]
    keep = by_case[(2, "provider_error", "keep_successful")]
    assert prefix["batches_completed"] == 2 and keep["batches_completed"] == 4
    assert keep["relations_total"] > prefix["relations_total"]
    assert keep["relations_delta"] == keep["relations_total"] - base["relations_total"]
    assert prefix["partial_means_rest_unclassified"] is True
    assert keep["partial_means_rest_unclassified"] is False
    assert keep["accepted_after_rejected"] == 2
    served = by_case[(0, "served_model_rejected", "keep_successful")]
    assert served["accepted_after_rejected"] == 4
    assert {r["kind"] for r in rows} == {None, *pairs_replay.KINDS}
    assert by_case[(1, "quota", "prefix")]["stopped_reason"] == "LLM_FALLBACK"


# R2.15 — KD3
def test_kd3_deadline_checked_at_submit():
    def run(conc):
        state = {"now": 1000.0}
        lock = threading.Lock()
        script = Script()

        def advance(_b: int) -> None:
            with lock:
                state["now"] += 5

        script.on_call = advance
        # deadline_required = 30 + 3 * 45 = 165: 172 -> 167 -> 162 cuts batch 2 sequentially.
        runtime_kw = {"max_processing_seconds": 172, "clock": lambda: state["now"]}
        return observe(conc, script=script, runtime_kw=runtime_kw)[0]

    seq, par = run(1), run(5)
    assert seq["batches_completed"] == 2 and seq["stopped_reason"] == "DEADLINE"
    # Known difference: the parallel run checked the deadline once, at submit.
    assert par["batches_completed"] == 5 and par["stopped_reason"] is None


# R2.16 — KD6 / F2
@pytest.mark.parametrize("branch", ["retry_ok", "retry_quota"])
def test_quota_during_lower_batch_backoff(branch):
    actions = {(1, 1): "rate_limited", (3, 1): "quota"}
    if branch == "retry_quota":
        actions[(1, 2)] = "quota"
    script = Script(actions=actions)
    runtime_kw = {"sleep": lambda _s: script.event("quota-3").wait(JOIN)}
    par, script = observe(5, script=script, runtime_kw=runtime_kw)
    codes = [code for code, _ in par["issues"]]
    assert script.attempts[1] == 2  # the lower batch still retried after the quota flip
    assert par["stopped_reason"] == "LLM_FALLBACK"
    assert codes == ["LLM_QUOTA_EXHAUSTED"]
    assert par["batches_completed"] == (3 if branch == "retry_ok" else 1)


# R2.17 — F3
@pytest.mark.parametrize("case", ["empty", "budget"])
def test_zero_planned_batches_take_sequential_path(monkeypatch, case):
    n, runtime_kw = (0, {}) if case == "empty" else (10, {"max_llm_calls": 0})
    seq, _ = observe(1, n=n, runtime_kw=runtime_kw)
    monkeypatch.setattr(pc, "ThreadPoolExecutor", _NoExecutor)
    par, _ = observe(5, n=n, runtime_kw=runtime_kw)
    assert par == seq
    if case == "budget":
        assert par["stopped_reason"] == "BUDGET_EXHAUSTED"


# R2.14 — KD2. PR #125 review round 2 (Chuongpham2004): budget 5, 5 batches, batch 2 (index 1) is
# throttled once. Later batches must not take the budget batch 2 needs to retry; the
# parallel run keeps batches 1-4 exactly like the sequential run.
@pytest.mark.parametrize("kind", ["rate_limited", "unavailable"])
def test_kd2_retry_keeps_its_budget_over_later_batches(kind):
    actions = {(1, 1): kind}
    seq, _ = observe(1, script=Script(actions=actions), runtime_kw={"max_llm_calls": 5})
    assert seq["batches_completed"] == 4 and seq["stopped_reason"] == "BUDGET_EXHAUSTED"
    for _ in range(3):
        par, script = observe(5, script=Script(actions=actions), runtime_kw={"max_llm_calls": 5})
        assert par["llm_calls_used"] <= 5
        assert script.attempts[1] == 2
        assert_equal_except_spend(par, seq)
