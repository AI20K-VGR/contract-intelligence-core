"""Live seeded gate for the pair classifier (paid LLM calls; not part of pytest).

    python -m fixtures.seeded.run_live --repeats 3

Runs every seeded dossier (dev and held-out) through the real pipeline ``--repeats`` times and, for every expected
relation, reports how often it was produced and, when missed, the stage it dropped out of
(not a candidate / cut by top-K / sent but labelled otherwise). Exit 1 when a ``must`` relation
is missed in any run or a ``forbidden`` one appears: the gate is "expected ⊆ produced and
forbidden ∩ produced = ∅", never an edge count.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from app.llm.client import NineRouterClient
from fixtures.seeded import funnel as seeded_funnel
from fixtures.seeded.common import context_caps_env
from fixtures.seeded.score import DOSSIERS


def _stage(funnel: seeded_funnel.Funnel, a: str, b: str) -> str:
    pair = {funnel.node(a), funnel.node(b)}
    if pair in [{x, y} for x, y in funnel.luong1]:
        return "luong1_edge"
    if not any({c.node_a, c.node_b} == pair for c in funnel.candidates):
        return "not_candidate_or_capped"
    events = [e for e in funnel.pair_events if {e.get("node_a_id"), e.get("node_b_id")} == pair]
    return (
        "sent:" + ",".join(sorted({str(e.get("outcome")) for e in events}))
        if events
        else "kept_not_sent"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    os.environ.setdefault("AI2_SEMANTIC_CONTEXT_CAPS", context_caps_env())
    llm = NineRouterClient()
    if not llm.configured():
        print("LLM not configured (AI2_LLM_API_KEY / OPENAI_API_KEY)", file=sys.stderr)
        return 2
    report, failed = [], False
    for split, modules in DOSSIERS.items():
        for module in modules:
            gold = module.LIVE_EXPECTED
            hits: Counter[tuple[str, str, str]] = Counter()
            misses: dict[tuple[str, str, str], Counter[str]] = {m: Counter() for m in gold["must"]}
            forbidden = 0
            for _ in range(args.repeats):
                funnel = seeded_funnel.run(module.request(egress_allowed=True), llm=llm)
                produced = {
                    (r.label.value, frozenset((r.node_a_id, r.node_b_id)))
                    for r in (funnel.pair_result.relations if funnel.pair_result else [])
                }
                for label, a, b in gold["must"]:
                    if (label, frozenset((funnel.node(a), funnel.node(b)))) in produced:
                        hits[(label, a, b)] += 1
                    else:
                        misses[(label, a, b)][_stage(funnel, a, b)] += 1
                for label, prefix in gold["forbidden_label_on"]:
                    forbidden += sum(
                        1
                        for lbl, ids in produced
                        if lbl == label and any(funnel.texts[i].startswith(prefix) for i in ids)
                    )
            failed = failed or forbidden or any(hits[m] < args.repeats for m in gold["must"])
            report.append(
                {
                    "dossier": module.DOSSIER_ID,
                    "split": split,
                    "repeats": args.repeats,
                    "must": [
                        {
                            "label": label,
                            "a": a,
                            "b": b,
                            "hits": hits[(label, a, b)],
                            "miss_stage": dict(misses[(label, a, b)]),
                        }
                        for label, a, b in gold["must"]
                    ],
                    "forbidden_hits": forbidden,
                }
            )
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
