"""The offline seeded scorer runs on every dossier; dev must stay fully green (held-out is only scored)."""

from __future__ import annotations

from fixtures.seeded import score


def test_scorer_covers_both_splits_and_dev_is_green(monkeypatch):
    monkeypatch.delenv("AI2_SEMANTIC_CONTEXT_CAPS", raising=False)
    checks = score.run()
    assert {c.split for c in checks} == {"dev", "heldout"}
    failed_dev = [f"{c.kind}: {c.expect} @{c.stage}" for c in checks if c.split == "dev" and not c.passed]
    assert not failed_dev, failed_dev
