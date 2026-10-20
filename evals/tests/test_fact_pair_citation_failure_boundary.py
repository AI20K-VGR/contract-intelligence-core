from pathlib import Path

import pytest

from evals.scripts.run_fact_pair_citation_eval import _score_case


def test_missing_snapshot_counts_only_contract_rejection(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "ai-service"))
    result = _score_case({"case": "missing", "snapshot": None, "expect": {}})
    assert result["checks"] == [("state", True)]


def test_unexpected_adapter_failure_is_not_scored_as_blocked(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "ai-service"))
    from app.pipeline import ai1_snapshot_adapter

    def broken_adapter(_snapshot):
        raise RuntimeError("unexpected adapter failure")

    monkeypatch.setattr(ai1_snapshot_adapter, "adapt_snapshot", broken_adapter)
    with pytest.raises(RuntimeError, match="unexpected adapter failure"):
        _score_case({"case": "missing", "snapshot": None, "expect": {}})
