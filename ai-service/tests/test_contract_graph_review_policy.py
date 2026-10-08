from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.contracts.contract_graph import ContractEdge, EdgeMethod, EdgeOp
from app.contracts.models import Citation, RelationSupport, ReviewState
from app.pipeline.contract_graph import review_policy
from app.pipeline.contract_graph.review_policy import (
    CALIBRATION_PATH,
    MIN_N,
    MIN_WILSON_LOWER,
    auto_pass_enabled,
    calibration_problems,
    load_calibration,
    review_state_for,
    wilson_lower,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _citation(status: str = "VALID") -> Citation:
    return Citation(node_id="n", page_revision_id="p", text_span="x", validation_status=status)


def _edge(**overrides) -> ContractEdge:
    values = dict(
        edge_id="cedge:1",
        op=EdgeOp.SUBSTITUTION,
        source_node_id="a1",
        target_node_id="b1",
        target_address="khoan 2 dieu 3",
        method=EdgeMethod.EXACT,
        support=RelationSupport.EXPLICIT_TEXT,
        standard=True,
        implicit=False,
        source_citation=_citation(),
        target_citation=_citation(),
        source_snapshot_digest="sha256:aaa",
    )
    values.update(overrides)
    return ContractEdge(**values)


def _calibration(n: int, k: int) -> dict:
    return {
        "schema": "contract-graph-calibration.v1",
        "ground_truth": "approved-only",
        "ops": {
            op.value: {"n": n, "k": k, "report": "evals/contract_graph/reports/p1-baseline.json"}
            for op in EdgeOp
        },
    }


def test_default_env_is_needs_review(monkeypatch):
    monkeypatch.delenv("AI2_CONTRACT_GRAPH_AUTO_PASS", raising=False)

    assert auto_pass_enabled() is False
    assert (
        review_state_for(_edge(), _calibration(60, 60), auto_pass_enabled())
        == ReviewState.NEEDS_REVIEW
    )


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", " On "])
def test_auto_pass_env_truthy(monkeypatch, value):
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_AUTO_PASS", value)

    assert auto_pass_enabled() is True


def test_committed_calibration_blocks_pass():
    calibration = load_calibration()

    assert calibration["schema"] == "contract-graph-calibration.v1"
    assert calibration["ground_truth"] == "approved-only"
    assert set(calibration["ops"]) == {op.value for op in EdgeOp}
    assert all(entry == {"n": 0, "k": 0, "report": None} for entry in calibration["ops"].values())
    for op in EdgeOp:
        assert review_state_for(_edge(op=op), calibration, True) == ReviewState.NEEDS_REVIEW


def test_pass_only_when_every_condition_holds():
    assert review_state_for(_edge(), _calibration(60, 60), True) == ReviewState.PASS


@pytest.mark.parametrize(
    ("calibration", "overrides", "enabled"),
    [
        (_calibration(59, 59), {}, True),
        (_calibration(60, 54), {}, True),
        (_calibration(60, 60), {"standard": False}, True),
        (_calibration(60, 60), {"method": EdgeMethod.ANCESTOR}, True),
        (_calibration(60, 60), {"method": EdgeMethod.ORDER_INFERENCE}, True),
        (_calibration(60, 60), {"method": EdgeMethod.SELF}, True),
        (_calibration(60, 60), {"method": EdgeMethod.ITEM_KEY}, True),
        (_calibration(60, 60), {"implicit": True}, True),
        (_calibration(60, 60), {"source_citation": _citation("INVALID")}, True),
        (_calibration(60, 60), {"target_citation": _citation("UNVERIFIED")}, True),
        (_calibration(60, 60), {}, False),
        ({**_calibration(60, 60), "ground_truth": "auto-gold"}, {}, True),
        (_calibration(60, 61), {}, True),
    ],
)
def test_each_missing_condition_blocks_pass(calibration, overrides, enabled):
    assert review_state_for(_edge(**overrides), calibration, enabled) == ReviewState.NEEDS_REVIEW


def test_wilson_lower_of_54_of_60_is_below_threshold():
    assert 0.79 < wilson_lower(54, 60) < 0.81
    assert wilson_lower(60, 60) >= MIN_WILSON_LOWER
    assert wilson_lower(0, 0) == 0.0


def test_thresholds_are_constants():
    assert MIN_N == 60
    assert MIN_WILSON_LOWER == 0.85
    source = inspect.getsource(review_policy)
    # literal module constants, never read from the environment
    assert "\nMIN_N = 60\n" in source and "\nMIN_WILSON_LOWER = 0.85\n" in source


def test_calibration_entries_with_n_reference_existing_report():
    assert calibration_problems(load_calibration(), REPO_ROOT) == []
    assert CALIBRATION_PATH.name == "calibration.json"
    bad = _calibration(60, 60)
    bad["ops"]["REPEAL"]["report"] = "evals/contract_graph/reports/missing.json"
    bad["ops"]["INSERTION"]["report"] = None

    assert calibration_problems(bad, REPO_ROOT) == [
        "INSERTION: n=60 without a report",
        "REPEAL: report evals/contract_graph/reports/missing.json does not exist",
    ]
