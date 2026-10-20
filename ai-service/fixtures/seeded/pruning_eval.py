"""Offline check of same-article pair pruning on ``pruning_set`` (no LLM).

    python -m fixtures.seeded.pruning_eval     # per split: gold lost, pairs and calls before -> after

Exit 1 when pruning drops a gold relation that was a candidate without it.
"""

from __future__ import annotations

import math
import os
from unittest import mock

from app.pipeline.contract_graph import pair_candidates
from app.pipeline.contract_graph.pair_classifier import PAIRS_PER_CALL
from fixtures.seeded import funnel as seeded_funnel
from fixtures.seeded import pruning_set
from fixtures.seeded.common import context_caps_env


def _candidates(dossier, *, prune: bool):
    with mock.patch.object(
        pair_candidates,
        "_same_article_related",
        pair_candidates._same_article_related if prune else (lambda *_a: True),
    ):
        funnel = seeded_funnel.run(dossier.request())
    gold = {frozenset((funnel.node(a), funnel.node(b))) for a, b in dossier.RELATED}
    pairs = {frozenset((c.node_a, c.node_b)) for c in funnel.candidates}
    return gold - {frozenset(p) for p in funnel.luong1}, pairs


def main() -> int:
    os.environ.setdefault("AI2_SEMANTIC_CONTEXT_CAPS", context_caps_env())
    failed = False
    for split in ("dev", "heldout"):
        lost = before = after = calls_before = calls_after = 0
        for dossier in (d for d in pruning_set.DOSSIERS if d.SPLIT == split):
            gold, base = _candidates(dossier, prune=False)
            _, kept = _candidates(dossier, prune=True)
            lost += len((gold & base) - kept)
            before, after = before + len(base), after + len(kept)
            calls_before += math.ceil(len(base) / PAIRS_PER_CALL)
            calls_after += math.ceil(len(kept) / PAIRS_PER_CALL)
        failed = failed or bool(lost)
        print(
            f"{split}: gold_lost {lost} pairs {before}->{after} calls {calls_before}->{calls_after}"
        )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
