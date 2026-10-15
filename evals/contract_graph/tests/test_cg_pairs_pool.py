from __future__ import annotations

import itertools
import os
import subprocess
import sys

from conftest import REPO_ROOT
from test_cg_pairs_corpus import contract_text, source

from evals.contract_graph.pairs import corpus, pool


def _doc(**kwargs):
    return corpus.build_doc(source(), contract_text(**kwargs))


def _ancestors(doc: dict) -> dict[str, set[str]]:
    parent = {n["node_id"]: n["parent_id"] for n in doc["nodes"]}
    out: dict[str, set[str]] = {}
    for node_id in parent:
        seen, walk = set(), parent[node_id]
        while walk is not None:
            seen.add(walk)
            walk = parent.get(walk)
        out[node_id] = seen
    return out


def _root(doc: dict) -> dict[str, str]:
    anc = _ancestors(doc)
    roots = {n["node_id"] for n in doc["nodes"] if n["parent_id"] is None}
    return {nid: nid if nid in roots else next(iter(a & roots)) for nid, a in anc.items()}


def _label(doc: dict, node_id: str) -> str:
    return next(n["raw_label"] for n in doc["nodes"] if n["node_id"] == node_id)


def _pairs(records, stratum=None):
    return {(r["a"], r["b"]) for r in records if stratum is None or r["stratum"] == stratum}


def test_same_article_stratum_is_exhaustive():
    doc = _doc()
    records, _ = pool.build_pool(doc)
    anc, root = _ancestors(doc), _root(doc)
    order = {n["node_id"]: n["order"] for n in doc["nodes"]}
    expected = {
        tuple(sorted((x, y), key=order.__getitem__))
        for x, y in itertools.combinations(order, 2)
        if root[x] == root[y]
        and _label(doc, root[x]).startswith("Điều")
        and x not in anc[y]
        and y not in anc[x]
    }

    assert _pairs(records, "S1") == expected
    # Điều 2: clauses 1, 2, 3 and points a), b) under clause 2 → 10 pairs minus 2 ancestor pairs
    article2 = next(n["node_id"] for n in doc["nodes"] if n["raw_label"] == "Điều 2")
    assert sum(1 for a, b in _pairs(records, "S1") if root[a] == article2) == 8


def test_body_annex_stratum_and_cap():
    doc = _doc()
    root = _root(doc)
    annex_nodes = {nid for nid, r in root.items() if _label(doc, r).startswith("Phụ lục")}
    body_nodes = set(root) - annex_nodes
    records, stats = pool.build_pool(doc)

    s2 = _pairs(records, "S2")
    assert s2 == {
        p for p in s2 if (p[0] in body_nodes) != (p[1] in body_nodes)
    }
    assert len(s2) == len(body_nodes) * len(annex_nodes)
    capped, capped_stats = pool.build_pool(doc, s2_cap=5)
    assert len(_pairs(capped, "S2")) == 5
    assert _pairs(capped, "S2") <= s2
    assert capped_stats["S2_universe"] == stats["S2_universe"] == len(s2)


def test_cross_article_sample_is_seeded_and_disjoint():
    doc = _doc()
    records, stats = pool.build_pool(doc)
    s3 = _pairs(records, "S3")

    assert len(s3) == min(pool.S3_N, stats["S3_universe"]) == pool.S3_N
    assert not s3 & (_pairs(records, "S1") | _pairs(records, "S2"))
    assert pool.build_pool(doc)[0] == records
    other_seed, _ = pool.build_pool(doc, seed=pool.POOL_SEED + 1)
    assert _pairs(other_seed, "S3") != s3
    assert _pairs(other_seed, "S1") == _pairs(records, "S1")
    root = _root(doc)
    # never inside one Điều (that is S1); two parts of the same Phụ lục may be S3
    assert all(root[a] != root[b] or _label(doc, root[a]).startswith("Phụ lục") for a, b in s3)


def test_ancestor_pairs_excluded():
    doc = _doc()
    anc = _ancestors(doc)
    records, _ = pool.build_pool(doc)

    assert records
    assert all(r["a"] not in anc[r["b"]] and r["b"] not in anc[r["a"]] for r in records)


def test_luong1_edge_pairs_excluded():
    doc = _doc(amend_in_annex=True)
    by_text = {n["text"][:12]: n["node_id"] for n in doc["nodes"]}
    amending = next(nid for t, nid in by_text.items() if t.startswith("Sửa đổi"))
    target = next(nid for t, nid in by_text.items() if t.startswith("Giá hợp đồng"))
    records, stats = pool.build_pool(doc)

    assert stats["excluded_luong1"] == 1
    assert (target, amending) not in _pairs(records)
    assert (amending, target) not in _pairs(records)
    plain, plain_stats = pool.build_pool(_doc())
    assert plain_stats["excluded_luong1"] == 0


def test_pool_records_carry_no_text():
    doc = _doc()
    records, _ = pool.build_pool(doc)

    assert {tuple(sorted(r)) for r in records} == {("a", "b", "doc_id", "pair_id", "stratum")}
    assert all(len(r["pair_id"]) == 16 for r in records)
    assert len({r["pair_id"] for r in records}) == len(records)
    order = {n["node_id"]: n["order"] for n in doc["nodes"]}
    assert all(order[r["a"]] < order[r["b"]] for r in records)


_HASH_SCRIPT = """
import sys
sys.path[:0] = [{root!r}, {root!r} + '/ai-service', {root!r} + '/evals/contract_graph/tests']
from test_cg_pairs_corpus import contract_text, source
from evals.contract_graph.pairs import corpus, pool
doc = corpus.build_doc(source(), contract_text(amend_in_annex=True))
records, _ = pool.build_pool(doc)
print(pool.pool_digest(records))
"""


def test_pool_stable_across_hash_seeds():
    script = _HASH_SCRIPT.format(root=str(REPO_ROOT).replace("\\", "/"))
    digests = []
    for seed in ("0", "7"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True
        )
        digests.append(out.stdout.strip())

    assert digests[0] == digests[1]
    assert len(digests[0]) == 64


def test_estimate_review_rows_applies_caps():
    pools, labels = [], []
    plan = [("GENERAL_SPECIFIC", "S1", 120), ("CONFLICT", "S2", 30), ("UNRELATED", "S1", 150),
            ("UNRELATED", "S2", 40), ("UNRELATED", "S3", 10), ("DUPLICATE", "S3", 1)]
    for label, stratum, n in plan:
        for i in range(n):
            pid = f"{label[:3]}{stratum}{i:04d}"
            pools.append({"pair_id": pid, "doc_id": "pd-x", "a": "x:n0", "b": "x:n1",
                          "stratum": stratum})
            labels.append({"pair_id": pid, "label": label, "label_invalid": False})
    pools.append({"pair_id": "BAD0", "doc_id": "pd-x", "a": "x:n0", "b": "x:n1", "stratum": "S1"})
    labels.append({"pair_id": "BAD0", "label": None, "label_invalid": True})

    est = pool.estimate_review_rows(pools, labels)

    assert est["by_label"]["GENERAL_SPECIFIC"] == {"gpt_positive": 120, "selected": 75}
    assert est["by_label"]["CONFLICT"] == {"gpt_positive": 30, "selected": 30}
    assert est["by_label"]["DUPLICATE"] == {"gpt_positive": 1, "selected": 1}
    assert est["by_label"]["REFERENCE"] == {"gpt_positive": 0, "selected": 0}
    assert est["unrelated"]["gpt_unrelated"] == 200
    assert est["unrelated"]["selected"] == 80
    assert est["total_rows"] == 75 + 30 + 1 + 80
    assert est["row_cap"] == 380
    assert est["over_cap"] is False
    assert est["includes_s4"] is False
