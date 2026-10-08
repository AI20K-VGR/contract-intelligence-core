"""Stratified pair pool of one doc (D17): unordered node pairs to be labeled, no text.

S1 every pair inside the same Điều; S2 body ↔ Phụ lục, capped at ``S2_CAP`` per doc; S3 a seeded
sample of ``min(S3_N, rest)`` remaining pairs. Ancestor–descendant pairs and pairs joined by a
luồng-1 edge (``plan_edges`` on the doc's ``StructureIndex``) never enter the pool. Sampling
draws from sorted lists with a per-doc ``random.Random`` so the pool is identical whatever
``PYTHONHASHSEED`` is.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
from collections import Counter
from collections.abc import Iterable

from evals.contract_graph.pairs import review
from evals.contract_graph.pairs.corpus import AI_SERVICE

POOL_SEED = 20261008
S2_CAP = 200
S3_N = 40
STRATA = ("S1", "S2", "S3")
POOL_PARAMS = {"S1": "all same-article pairs", "S2_cap_per_doc": S2_CAP, "S3_per_doc": S3_N}
_NODE_FIELDS = ("node_id", "type", "raw_label", "parent_id", "order", "text", "source_file_id",
                "page_range")


def pair_id_for(doc_id: str, a: str, b: str) -> str:
    return hashlib.sha256(f"{doc_id}|{a}|{b}".encode("utf-8")).hexdigest()[:16]


def build_pool(
    doc: dict, *, seed: int = POOL_SEED, s2_cap: int = S2_CAP, s3_n: int = S3_N
) -> tuple[list[dict], dict]:
    """``(records, stats)``; records ``{pair_id, doc_id, a, b, stratum}`` sorted by stratum then
    node order. ``stats`` has each stratum's universe and kept size and ``excluded_luong1``."""

    doc_id = doc["doc_id"]
    nodes = sorted(doc["nodes"], key=lambda n: n["order"])
    parent = {n["node_id"]: n["parent_id"] for n in nodes}
    label = {n["node_id"]: n["raw_label"] for n in nodes}
    order = {n["node_id"]: n["order"] for n in nodes}
    ancestors = {nid: _ancestors(nid, parent) for nid in parent}
    root = {nid: ([nid, *ancestors[nid]][-1]) for nid in parent}
    luong1 = luong1_pairs(doc)

    strata: dict[str, list[tuple[str, str]]] = {s: [] for s in STRATA}
    excluded = 0
    for a, b in itertools.combinations([n["node_id"] for n in nodes], 2):
        if a in ancestors[b] or b in ancestors[a]:
            continue
        if (a, b) in luong1:
            excluded += 1
            continue
        ra, rb = root[a], root[b]
        if ra == rb and _is_article(label[ra]):
            strata["S1"].append((a, b))
        elif _is_article(label[ra]) != _is_article(label[rb]):
            strata["S2"].append((a, b))
        else:
            strata["S3"].append((a, b))

    rng = random.Random(seed ^ int(hashlib.sha256(doc_id.encode("utf-8")).hexdigest()[:8], 16))
    kept = {
        "S1": strata["S1"],
        "S2": _sample(rng, strata["S2"], s2_cap),
        "S3": _sample(rng, strata["S3"], s3_n),
    }
    records = [
        {"pair_id": pair_id_for(doc_id, a, b), "doc_id": doc_id, "a": a, "b": b, "stratum": s}
        for s in STRATA
        for a, b in sorted(kept[s], key=lambda p: (order[p[0]], order[p[1]]))
    ]
    stats = {"excluded_luong1": excluded}
    for s in STRATA:
        stats[f"{s}_universe"] = len(strata[s])
        stats[s] = len(kept[s])
    return records, stats


def _ancestors(node_id: str, parent: dict[str, str | None]) -> list[str]:
    out, walk = [], parent.get(node_id)
    while walk is not None and walk not in out:
        out.append(walk)
        walk = parent.get(walk)
    return out


def _is_article(raw_label: str) -> bool:
    return raw_label.startswith("Điều ")


def _sample(rng: random.Random, pairs: list[tuple[str, str]], k: int) -> list[tuple[str, str]]:
    ordered = sorted(pairs)
    return ordered if len(ordered) <= k else rng.sample(ordered, k)


def luong1_pairs(doc: dict) -> set[tuple[str, str]]:
    """Node pairs (in document order) joined by a resolved luồng-1 edge of the doc, the doc file
    in role ``body`` (annex parts come from its Phụ lục headings)."""

    StructuralNode, builder, resolver = _app()
    nodes = [StructuralNode(**{k: n[k] for k in _NODE_FIELDS if k in n}) for n in doc["nodes"]]
    index = resolver.StructureIndex.build(nodes, {doc["doc_id"]: "body"})
    order = {n["node_id"]: n["order"] for n in doc["nodes"]}
    pairs = set()
    for plan in builder.plan_edges(nodes, index):
        target = plan.target_node_id
        if target is None or target == plan.source_node_id or target not in order:
            continue
        pairs.add(tuple(sorted((plan.source_node_id, target), key=order.__getitem__)))
    return pairs


def pool_digest(records: Iterable[dict]) -> str:
    lines = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def estimate_review_rows(pools: Iterable[dict], labels: Iterable[dict]) -> dict:
    """HG-1 rows the D18 rule would select from these labels (RT-12), before the S4 extension.
    Same rule as ``review.select_for_review``; only labels of pool pairs count."""

    pooled_by_id = {r["pair_id"]: r for r in pools}
    by_stratum: dict[str, list[dict]] = {}
    positives: Counter[str] = Counter()
    n_unrelated = 0
    for record in labels:
        pooled = pooled_by_id.get(record["pair_id"])
        if pooled is None or record.get("label_invalid") or record.get("label") not in review.LABELS:
            continue
        by_stratum.setdefault(pooled["stratum"], []).append({**pooled, **record})
        if record["label"] == review.UNRELATED:
            n_unrelated += 1
        else:
            positives[record["label"]] += 1
    selection = review.select_for_review(by_stratum, POOL_SEED, row_cap=None)
    chosen = Counter(r["gpt_label"] for r in selection)
    return {
        "by_label": {
            label: {"gpt_positive": positives[label], "selected": chosen[label]}
            for label in review.POSITIVE_LABELS
        },
        "unrelated": {
            "gpt_unrelated": n_unrelated,
            "selected": chosen[review.UNRELATED],
            "by_stratum": dict(sorted(Counter(r["stratum"] for r in selection
                                              if r["gpt_label"] == review.UNRELATED).items())),
        },
        "total_rows": len(selection),
        "row_cap": review.REVIEW_ROW_CAP,
        "over_cap": len(selection) > review.REVIEW_ROW_CAP,
        "includes_s4": False,
    }


def _app():
    if str(AI_SERVICE) not in sys.path:
        sys.path.insert(0, str(AI_SERVICE))
    from app.contracts.models import StructuralNode
    from app.pipeline.contract_graph import builder, resolver

    return StructuralNode, builder, resolver
