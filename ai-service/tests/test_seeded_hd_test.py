"""Seeded-defect gate for HD-TEST-2026-001 (offline, deterministic stages only).

A passing graph is "expected ⊆ produced and forbidden ∩ produced = ∅", not "N edges". Each
expectation is its own test so a failure names the stage it dropped out of. The classifier
(LLM) stage is checked live by ``python -m fixtures.seeded.run_live``.
"""

from __future__ import annotations

import pytest

from fixtures.seeded import funnel as seeded_funnel
from fixtures.seeded import hd_test_2026_001 as hd

EXPECTED = hd.EXPECTED


@pytest.fixture(scope="module")
def funnel():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AI2_SEMANTIC_CONTEXT_CAPS", hd.context_caps_env())
        mp.delenv("AI2_CONTRACT_GRAPH_PAIRS_API_KEY", raising=False)
        mp.delenv("AI2_CONTRACT_GRAPH_PAIRS_BASE_URL", raising=False)
        return seeded_funnel.run(hd.request())


@pytest.mark.parametrize(("amending", "target"), EXPECTED["luong1_must"])
def test_luong1_operation_edge(funnel, amending, target):
    edge = (funnel.node(amending), funnel.node(target))
    assert edge in funnel.luong1, [tuple(map(funnel.describe, e)) for e in funnel.luong1]


@pytest.mark.parametrize(("clause", "slots"), EXPECTED["frame_slots"])
def test_frame_carries_planted_value(funnel, clause, slots):
    frames = funnel.frames_of(clause)
    assert frames, f"no semantic frame for {clause!r}"
    seen = [{name: frame.slots[name].value for name in slots} for frame in frames]
    assert slots in seen, seen


@pytest.mark.parametrize(("clause", "tail"), EXPECTED["clause_complete"])
def test_wrapped_clause_is_one_node(funnel, clause, tail):
    assert tail in funnel.texts[funnel.node(clause)]


@pytest.mark.parametrize(("left", "right", "slot"), EXPECTED["semantic_difference"])
def test_planted_value_change_reaches_review(funnel, left, right, slot):
    left_ids = {f.frame_id for f in funnel.frames_of(left)}
    right_ids = {f.frame_id for f in funnel.frames_of(right)}
    pairs = [p for p in funnel.semantic_pairs
             if {p.left_id, p.right_id} & left_ids and {p.left_id, p.right_id} & right_ids]
    assert pairs, "the two clauses were never compared"
    assert any(p.disposition in {"COMPARABLE_DIFFERENCE", "CONFLICT_CANDIDATE"} and slot in p.reason
               for p in pairs), [(p.disposition, p.reason) for p in pairs]


@pytest.mark.parametrize(("a", "b"), EXPECTED["candidates_must_keep"])
def test_candidate_survives_top_k(funnel, a, b):
    assert funnel.has_candidate(a, b), (
        f"{a!r} <-> {b!r} not among {len(funnel.candidates)} kept candidates"
    )


@pytest.mark.parametrize("furniture", EXPECTED["never_candidate"])
def test_page_furniture_is_never_a_candidate(funnel, furniture):
    touching = [
        (funnel.describe(c.node_a), funnel.describe(c.node_b)) for c in funnel.candidates
        if funnel.texts[c.node_a].startswith(furniture) or funnel.texts[c.node_b].startswith(furniture)
    ]
    assert not touching, touching


@pytest.mark.parametrize(("a", "b"), EXPECTED["never_value_mismatch"])
def test_clause_numbers_are_not_value_mismatches(monkeypatch, a, b):
    # Judged on the uncapped set: the cap must not be what hides the noise.
    monkeypatch.setenv("AI2_SEMANTIC_CONTEXT_CAPS", hd.context_caps_env())
    from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
    from app.pipeline.contract_graph.pair_candidates import PairSource, generate_pair_candidates
    from app.pipeline.contract_graph.resolver import StructureIndex

    payload = hd.request()
    env = payload["service_envelope"]
    record = adapt_be_ai2_processing_request(payload, tenant_id=env["tenant_id"], actor_id=env["actor_id"])[1].record
    nodes = list(record.evidence_nodes())
    texts = {n.node_id: " ".join(n.text.split()) for n in nodes}
    ids = {prefix: next(nid for nid, t in texts.items() if t.startswith(prefix)) for prefix in (a, b)}
    index = StructureIndex.build(nodes, {s.file_id: s.role for s in record.source_files})
    sources = [c.sources for c in generate_pair_candidates(index, nodes, top_k=10_000).candidates
               if {c.node_a, c.node_b} == set(ids.values())]
    assert all(PairSource.VALUE_MISMATCH not in s for s in sources), sources
