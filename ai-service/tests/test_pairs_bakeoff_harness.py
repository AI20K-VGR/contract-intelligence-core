"""P3 pairs bake-off harness (fixtures/perf/pairs_bakeoff.py): config, guards, decision rule."""

from __future__ import annotations

import json
import os

import pytest

from app.pipeline.contract_graph import pair_classifier as pc
from fixtures.perf import pairs_bakeoff as bk

ROUTER = "http://host.docker.internal:20128/v1"
EFFORT = "AI2_PAIRS_REASONING_EFFORT"
MODEL = "AI2_CONTRACT_GRAPH_PAIRS_MODEL"


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    for key in (EFFORT, MODEL, "AI2_PERF_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    for key in bk.ROUTER_ENVS:
        monkeypatch.setenv(key, ROUTER)
    monkeypatch.setenv("AI2_PERF_DIR", str(tmp_path))


# R3.7a
@pytest.mark.parametrize(
    ("candidate", "check"),
    [
        ("C0", lambda: os.getenv(EFFORT) is None and pc.PAIRS_PER_CALL == 8),
        ("C1", lambda: os.getenv(EFFORT) == "low" and pc.PAIRS_PER_CALL == 8),
        ("C2", lambda: os.getenv(EFFORT) is None and pc.PAIRS_PER_CALL == 10),
        ("C3", lambda: os.getenv(MODEL) == "gh/gpt-5-mini" and pc.PAIRS_PER_CALL == 8),
    ],
)
def test_apply_and_restore_candidate(monkeypatch, candidate, check):
    monkeypatch.setenv(MODEL, "cx/gpt-5.6-luna")
    with bk.applied(candidate):
        assert check()
    assert os.getenv(EFFORT) is None
    assert os.getenv(MODEL) == "cx/gpt-5.6-luna"
    assert pc.PAIRS_PER_CALL == 8


def test_apply_restores_after_error(monkeypatch):
    monkeypatch.setenv(EFFORT, "medium")
    with pytest.raises(RuntimeError), bk.applied("C2"):
        raise RuntimeError("boom")
    assert pc.PAIRS_PER_CALL == 8 and os.getenv(EFFORT) == "medium"
    with bk.applied("C1"):
        assert os.getenv(EFFORT) == "low"
    assert os.getenv(EFFORT) == "medium"


def test_unknown_candidate_rejected():
    with pytest.raises(SystemExit), bk.applied("C9"):
        pass


# R3.7b
def test_trial_prints_exactly_one_number(monkeypatch, capsys, tmp_path):
    row = {"wall_s": 12.345, "calls": 23, "pairs_per_call_observed": 8}
    monkeypatch.setattr(bk, "run_job", lambda request_file: dict(row))
    bk.main(["trial", "--candidate", "C1", "--request-file", "x.json", "--run", "r1"])
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["12.345"]
    lines = (tmp_path / "bakeoff-r1.jsonl").read_text(encoding="utf-8").splitlines()
    saved = json.loads(lines[0])
    assert saved["candidate"] == "C1" and saved["calls"] == 23 and saved["wall_s"] == 12.345


# R3.7c
@pytest.mark.parametrize(
    "argv",
    [
        ["trial", "--candidate", "C0", "--request-file", "x.json", "--run", "r"],
        ["rank", "--run", "r"],
        ["drift", "--run", "r", "--candidate", "C1"],
        ["gate", "--candidate", "C0"],
    ],
)
@pytest.mark.parametrize("bad", [None, "https://api.openai.com/v1"])
def test_router_only_guard(monkeypatch, argv, bad):
    if bad is None:
        monkeypatch.delenv(bk.ROUTER_ENVS[0])
    else:
        monkeypatch.setenv(bk.ROUTER_ENVS[0], bad)
    monkeypatch.setattr(bk, "run_job", lambda _f: pytest.fail("must not run"))
    monkeypatch.setattr(bk, "run_gate", lambda: pytest.fail("must not run"))
    with pytest.raises(SystemExit, match="20128"):
        bk.main(argv)


# R3.7d
@pytest.mark.parametrize(
    "model", ["gpt-4o-mini-2024-07-18", "openai/gpt-4o-mini-2024-07-18", "unknown-model"]
)
def test_c3_rejects_labeler_and_unknown_family(model):
    with pytest.raises(SystemExit):
        bk.validate_c3_model(model)


def test_c3_accepts_small_gpt5():
    bk.validate_c3_model("gh/gpt-5-mini")


# R3.7e
def test_decide_clear_win():
    inc = [30, 31, 32, 33, 34, 35, 36, 37, 38, 40]
    cand = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    result = bk.decide(inc, cand)
    assert result["verdict"] == "WIN"
    assert result["p90_incumbent"] == 38 and result["p90_candidate"] == 23
    assert result["delta"] == 15 and result["ci_low"] > 0


def test_decide_overlap_is_tie():
    inc = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
    cand = [20.5, 21, 22, 23, 24, 25, 26, 27, 28, 29]
    assert bk.decide(inc, cand)["verdict"] == "TIE"


def test_decide_small_but_significant_delta_is_tie():
    inc = [20.0] * 9 + [20.0]
    cand = [19.9] * 10
    result = bk.decide(inc, cand)
    assert result["ci_low"] > 0 and result["verdict"] == "TIE"  # < 5 % of p90


def test_decide_slower_is_keep():
    inc = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    cand = [30, 31, 32, 33, 34, 35, 36, 37, 38, 40]
    assert bk.decide(inc, cand)["verdict"] == "KEEP"


def test_decide_is_deterministic():
    inc = [20, 25, 21, 30, 22, 26, 24, 27, 23, 29]
    cand = [19, 26, 20, 28, 25, 22, 21, 24, 27, 23]
    assert bk.decide(inc, cand) == bk.decide(inc, cand)


def test_rank_reads_jsonl(tmp_path, capsys):
    rows = [{"candidate": "C0", "wall_s": w} for w in range(30, 40)]
    rows += [{"candidate": "C1", "wall_s": w} for w in range(10, 20)]
    (tmp_path / "bakeoff-r.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8"
    )
    bk.main(["rank", "--run", "r"])
    out = capsys.readouterr().out
    assert "verdict=WIN:C1" in out


# R3.7f
TODAY = "2026-10-18"


def _openai_env(monkeypatch):
    monkeypatch.setenv("AI2_PERF_PROVIDER", "openai")
    for key in bk.ROUTER_ENVS:
        monkeypatch.setenv(key, "https://api.openai.com/v1")
    monkeypatch.setenv(MODEL, "gpt-5.5")
    monkeypatch.setenv("AI2_LLM_MODEL", "gpt-5.5")


def test_confirm_guard_accepts_complete_permission(monkeypatch):
    _openai_env(monkeypatch)
    bk.confirm_guard("C1", TODAY, today=TODAY)


@pytest.mark.parametrize(
    "breaker",
    [
        lambda m: m.delenv("AI2_PERF_PROVIDER"),
        lambda m: m.setenv("AI2_PERF_PROVIDER", "router"),
        lambda m: m.setenv(bk.ROUTER_ENVS[0], ROUTER),
        lambda m: m.setenv(bk.ROUTER_ENVS[1], "https://evil.example/v1"),
        lambda m: m.setenv(MODEL, "gpt-5-mini"),
        lambda m: m.setenv("AI2_LLM_MODEL", "gpt-4o"),
    ],
)
def test_confirm_guard_rejects_wrong_env(monkeypatch, breaker):
    _openai_env(monkeypatch)
    breaker(monkeypatch)
    with pytest.raises(SystemExit):
        bk.confirm_guard("C1", TODAY, today=TODAY)


@pytest.mark.parametrize(
    ("candidate", "permission"),
    [("C1", None), ("C1", "2026-10-17"), ("C1", "yes"), ("C3", TODAY), ("C0", TODAY)],
)
def test_confirm_guard_rejects_bad_permission_or_candidate(monkeypatch, candidate, permission):
    _openai_env(monkeypatch)
    with pytest.raises(SystemExit):
        bk.confirm_guard(candidate, permission, today=TODAY)


def test_confirm_requires_permission_flag():
    with pytest.raises(SystemExit):
        bk.main(["confirm-openai", "--candidate", "C1"])


# R3.7g
def test_c2_batch_assert():
    bk.check_batch("C2", 10)
    bk.check_batch("C0", 8)
    with pytest.raises(SystemExit, match="10"):
        bk.check_batch("C2", 8)


def test_c2_trial_errors_when_patch_had_no_effect(monkeypatch, tmp_path):
    monkeypatch.setattr(bk, "run_job", lambda _f: {"wall_s": 1.0, "pairs_per_call_observed": 8})
    with pytest.raises(SystemExit):
        bk.main(["trial", "--candidate", "C2", "--request-file", "x.json", "--run", "r2"])


def test_batch_observer_sees_patched_size():
    pairs = list(range(43))
    seen: list[int] = []
    with bk.applied("C2"), bk.observe_batches(seen):
        for offset in range(0, len(pairs), pc.PAIRS_PER_CALL):
            pc._batch_messages(_fake_pairs(43), offset)
    assert max(seen) == 10
    assert pc._batch_messages is bk.ORIGINAL_BATCH_MESSAGES


def _fake_pairs(n):
    from app.pipeline.contract_graph.pair_candidates import PairCandidate, PairSource
    from app.pipeline.contract_graph.pair_classifier import ClassifierPair

    return [
        ClassifierPair(
            PairCandidate(f"a{i}", f"b{i}", frozenset({PairSource.SAME_KEY}), 1.0, None, None),
            "text a",
            "text b",
            "ctx a",
            "ctx b",
        )
        for i in range(n)
    ]


# R3.7h
def _row(total, labels, ungrounded=0, no_answer=0):
    return {
        "relations_total": total,
        "relations_by_label": labels,
        "rejected": {"ungrounded_span": ungrounded, "no_answer": no_answer},
    }


def test_drift_within_band():
    inc = [_row(10, {"CONFLICT": 4, "DUPLICATE": 3})] * 3
    cand = [_row(9, {"CONFLICT": 3, "DUPLICATE": 3}, ungrounded=2)] * 3
    assert bk.drift(inc, cand)["flags"] == []


@pytest.mark.parametrize(
    ("cand", "flag"),
    [
        (_row(7, {"CONFLICT": 4, "DUPLICATE": 3}), "relations_total"),
        (_row(10, {"CONFLICT": 2, "DUPLICATE": 3}), "label:CONFLICT"),
        (_row(10, {"CONFLICT": 4, "DUPLICATE": 3}, ungrounded=2, no_answer=1), "rejected"),
    ],
)
def test_drift_flags(cand, flag):
    inc = [_row(10, {"CONFLICT": 4, "DUPLICATE": 3})] * 3
    flags = bk.drift(inc, [cand] * 3)["flags"]
    assert any(f.startswith(flag) for f in flags)
