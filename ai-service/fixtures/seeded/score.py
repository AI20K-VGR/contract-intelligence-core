"""Offline seeded-defect scorer: one number for the dev split, one for the held-out split.

    python -m fixtures.seeded.score            # human report + last line "SCORE <dev>"
    python -m fixtures.seeded.score --json     # one JSON object per expectation

Deterministic (``llm=None``): it scores what AI2 extracts, links and proposes before any model
call. Every expectation names the stage it dropped out of, so a miss is attributable. The gold
(``EXPECTED`` in each dossier module) is read-only for anything that optimizes against this score.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

from fixtures.seeded import funnel as seeded_funnel
from fixtures.seeded import hd_test_2026_001, hd_test_2026_002
from fixtures.seeded.common import context_caps_env

DOSSIERS = {"dev": [hd_test_2026_001], "heldout": [hd_test_2026_002]}


@dataclass
class Check:
    dossier: str
    split: str
    kind: str
    expect: str
    passed: bool
    stage: str
    detail: str = ""


def _ids(f: seeded_funnel.Funnel, *prefixes: str) -> list[str] | str:
    try:
        return [f.node(p) for p in prefixes]
    except LookupError as exc:
        return str(exc)


def _uncapped(record: Any):
    from app.pipeline.contract_graph.pair_candidates import generate_pair_candidates
    from app.pipeline.contract_graph.resolver import StructureIndex

    nodes = list(record.evidence_nodes())
    index = StructureIndex.build(nodes, {s.file_id: s.role for s in record.source_files})
    return generate_pair_candidates(index, nodes, top_k=10_000).candidates


def _checks(module, split: str) -> list[Check]:
    f = seeded_funnel.run(module.request())
    gold, name, out = module.EXPECTED, module.DOSSIER_ID, []

    def add(kind, expect, passed, stage, detail=""):
        out.append(Check(name, split, kind, expect, bool(passed), stage, detail))

    for a, b in gold.get("luong1_must", []):
        ids = _ids(f, a, b)
        add("luong1_must", f"{a} -> {b}", not isinstance(ids, str) and tuple(ids) in f.luong1,
            "structure" if isinstance(ids, str) else "luong1", ids if isinstance(ids, str) else "")
    for a, b in gold.get("luong1_forbidden", []):
        ids = _ids(f, a, b)
        add("luong1_forbidden", f"not {a} -> {b}", not isinstance(ids, str) and tuple(ids) not in f.luong1,
            "structure" if isinstance(ids, str) else "luong1", ids if isinstance(ids, str) else "")
    for clause, tail in gold.get("clause_complete", []):
        ids = _ids(f, clause)
        add("clause_complete", f"{clause} …{tail}",
            not isinstance(ids, str) and tail in f.texts[ids[0]], "structure",
            ids if isinstance(ids, str) else f.texts[ids[0]][-60:])
    for clause, slots in gold.get("frame_slots", []):
        ids = _ids(f, clause)
        frames = [] if isinstance(ids, str) else f.frames_of(clause)
        seen = [{k: fr.slots[k].value for k in slots} for fr in frames]
        add("frame_slots", f"{clause} {slots}", slots in seen, "semantic_extract", str(seen)[:120])
    for left, right, slot in gold.get("semantic_difference", []):
        ids = _ids(f, left, right)
        pairs = []
        if not isinstance(ids, str):
            lids = {fr.frame_id for fr in f.frames_of(left)}
            rids = {fr.frame_id for fr in f.frames_of(right)}
            pairs = [p for p in f.semantic_pairs
                     if {p.left_id, p.right_id} & lids and {p.left_id, p.right_id} & rids]
        ok = any(p.disposition in {"COMPARABLE_DIFFERENCE", "CONFLICT_CANDIDATE"} and slot in p.reason for p in pairs)
        add("semantic_difference", f"{left} <> {right} on {slot}", ok,
            "semantic_compare" if pairs else "semantic_candidates",
            str([(p.disposition, p.reason) for p in pairs])[:120])
    for a, b in gold.get("candidates_must_keep", []):
        ids = _ids(f, a, b)
        kept = not isinstance(ids, str) and any({c.node_a, c.node_b} == set(ids) for c in f.candidates)
        found = not isinstance(ids, str) and any({c.node_a, c.node_b} == set(ids) for c in _uncapped(f.record))
        add("candidates_must_keep", f"{a} <> {b}", kept,
            "pairs_cap" if found and not kept else "pairs_candidates")
    for a, b in gold.get("related_any", []):
        ids = _ids(f, a, b)
        ok = not isinstance(ids, str) and (
            tuple(ids) in f.luong1 or tuple(reversed(ids)) in f.luong1
            or any({c.node_a, c.node_b} == set(ids) for c in f.candidates))
        add("related_any", f"{a} ~ {b}", ok, "luong1+pairs_candidates")
    for code, a, b in gold.get("issues_must", []):
        ids = _ids(f, a, b)
        ok = not isinstance(ids, str) and any(
            i.code == code and i.evidence_refs == ids for i in f.record.handoff_issues)
        add("issues_must", f"{code} {a} | {b}", ok, "structure_issues")
    for prefix in gold.get("never_candidate", []):
        bad = [c for c in f.candidates if f.texts[c.node_a].startswith(prefix) or f.texts[c.node_b].startswith(prefix)]
        add("never_candidate", f"no candidate on {prefix!r}", not bad, "pairs_candidates", f"{len(bad)} hits")
    from app.pipeline.contract_graph.pair_candidates import PairSource

    for a, b in gold.get("never_value_mismatch", []):
        ids = _ids(f, a, b)
        bad = not isinstance(ids, str) and any(
            {c.node_a, c.node_b} == set(ids) and PairSource.VALUE_MISMATCH in c.sources for c in _uncapped(f.record))
        add("never_value_mismatch", f"{a} <> {b}", not bad, "pairs_candidates")
    return out


def run() -> list[Check]:
    os.environ.setdefault("AI2_SEMANTIC_CONTEXT_CAPS", context_caps_env())
    for name in ("AI2_CONTRACT_GRAPH_PAIRS_API_KEY", "AI2_CONTRACT_GRAPH_PAIRS_BASE_URL"):
        os.environ.pop(name, None)
    return [check for split, modules in DOSSIERS.items() for module in modules for check in _checks(module, split)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = run()
    if args.json:
        for c in checks:
            print(json.dumps(c.__dict__, ensure_ascii=False))
    else:
        for c in checks:
            if not c.passed:
                print(f"FAIL [{c.split}] {c.dossier} {c.kind} @{c.stage}: {c.expect} | {c.detail}")
    score = {}
    for split in DOSSIERS:
        rows = [c for c in checks if c.split == split]
        score[split] = (sum(c.passed for c in rows), len(rows))
        print(f"{split}: {score[split][0]}/{score[split][1]}")
    dev_ok, dev_total = score["dev"]
    print(f"SCORE {dev_ok / dev_total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
