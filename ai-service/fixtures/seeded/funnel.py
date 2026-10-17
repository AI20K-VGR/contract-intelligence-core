"""Run a seeded request through ``run_idp`` and record what every AI2 stage produced.

The funnel answers "where did an expected relation drop out": operation edges (luồng 1),
pair candidates before/after the top-K cap, classifier events (live only), semantic frames
and their comparisons. Offline runs pass ``llm=None`` and need no network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from unittest import mock

from app.pipeline import idp
from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
from app.pipeline.contract_graph import builder, pair_builder
from app.pipeline.runtime import ProcessingRuntime
from app.tools.store import InMemorySnapshotStore


@dataclass
class Funnel:
    texts: dict[str, str]
    luong1: list[tuple[str, str]] = field(default_factory=list)
    candidates: list[Any] = field(default_factory=list)
    pair_events: list[dict[str, Any]] = field(default_factory=list)
    pair_result: Any = None
    result: Any = None
    record: Any = None
    envelope: Any = None

    def node(self, prefix: str) -> str:
        """The single node whose normalized text starts with ``prefix``."""
        hits = [nid for nid, text in self.texts.items() if text.startswith(prefix)]
        if len(hits) != 1:
            raise LookupError(f"{prefix!r} matches {len(hits)} nodes")
        return hits[0]

    @property
    def frames(self):
        ext = self.result.contribution.semantic_extension
        return ext.frames if ext else []

    @property
    def semantic_pairs(self):
        ext = self.result.contribution.semantic_extension
        return ext.pairs if ext else []

    def frames_of(self, prefix: str):
        nid = self.node(prefix)
        return [f for f in self.frames if any(e.source_ref.split("#")[0] == nid for e in f.evidence)]

    def has_candidate(self, a: str, b: str) -> bool:
        pair = {self.node(a), self.node(b)}
        return any({c.node_a, c.node_b} == pair for c in self.candidates)

    def describe(self, node_id: str) -> str:
        return self.texts.get(node_id, node_id)[:80]


def run(payload: dict, *, llm: Any = None, runtime: ProcessingRuntime | None = None) -> Funnel:
    env = payload["service_envelope"]
    request, adapted = adapt_be_ai2_processing_request(
        payload, tenant_id=env["tenant_id"], actor_id=env["actor_id"]
    )
    record = adapted.record
    funnel = Funnel({n.node_id: " ".join(n.text.split()) for n in record.evidence_nodes()}, record=record,
                    envelope=adapted.envelope)
    real_graph = builder.build_contract_graph
    real_pairs = pair_builder.build_pair_relations
    real_candidates = pair_builder.generate_pair_candidates

    def graph_spy(*args, **kwargs):
        graph = real_graph(*args, **kwargs)
        funnel.luong1 = [(e.source_node_id, e.target_node_id) for e in graph.edges]
        return graph

    def candidates_spy(*args, **kwargs):
        result = real_candidates(*args, **kwargs)
        funnel.candidates = list(result.candidates)
        return result

    def pairs_spy(*args, **kwargs):
        funnel.pair_result = real_pairs(*args, event_sink=funnel.pair_events.append, **kwargs)
        return funnel.pair_result

    budget = request.policy_flags.budget_limits
    runtime = runtime or ProcessingRuntime(
        egress_allowed=llm is not None,
        use_vector=False,
        max_processing_seconds=budget.max_processing_seconds,
        max_llm_calls=budget.max_llm_calls if llm is not None else 0,
    )
    with (
        mock.patch.object(builder, "build_contract_graph", graph_spy),
        mock.patch.object(pair_builder, "generate_pair_candidates", candidates_spy),
        mock.patch.object(pair_builder, "build_pair_relations", pairs_spy),
        mock.patch.dict(os.environ, {"AI2_CONTRACT_GRAPH_ENABLED": "true",
                                     "AI2_CONTRACT_GRAPH_PAIRS_ENABLED": "true",
                                     "AI2_SEMANTIC_ENABLED": "true"}),
    ):
        funnel.result = idp.run_idp(
            record, adapted.envelope, llm=llm, store=InMemorySnapshotStore(),
            job_id="seeded", runtime=runtime,
        )
    return funnel
