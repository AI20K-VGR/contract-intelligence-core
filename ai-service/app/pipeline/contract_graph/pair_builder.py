"""Pair-candidate → consent-gated classifier → verified, review-only proposals."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from app.contracts.contract_graph import PairLabel, PairRelation, PairResult, pair_relation_id_for
from app.contracts.models import Citation
from app.llm.client import NineRouterClient
from app.pipeline.citations import CitationResolver
from app.pipeline.contract_graph.pair_candidates import (
    ALL_SOURCES,
    PAIRS_TOP_K,
    PairCandidateSet,
    PairSource,
    clause_context,
    generate_pair_candidates,
)
from app.pipeline.contract_graph.pair_classifier import (
    PAIRS_MAX_CALLS,
    PROMPT_VERSION,
    ClassifierPair,
    classifier_stats,
    classify_pairs,
    deadline_required,
)
from app.pipeline.contract_graph.resolver import StructureIndex
from app.pipeline.outline import citation_for_node
from app.pipeline.runtime import ProcessingRuntime
from app.tools.store import DossierRecord

PAIRS_ENV = "AI2_CONTRACT_GRAPH_PAIRS_ENABLED"
PAIRS_MODEL_ENV = "AI2_CONTRACT_GRAPH_PAIRS_MODEL"
PAIRS_BASE_URL_ENV = "AI2_CONTRACT_GRAPH_PAIRS_BASE_URL"
PAIRS_API_KEY_ENV = "AI2_CONTRACT_GRAPH_PAIRS_API_KEY"


def pairs_enabled() -> bool:
    return os.getenv(PAIRS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def classifier_client(llm: Any, model: str | None) -> Any:
    base, key = os.getenv(PAIRS_BASE_URL_ENV), os.getenv(PAIRS_API_KEY_ENV)
    if base and key:
        return NineRouterClient(base_url=base, api_key=key, model=model)
    if isinstance(llm, NineRouterClient):
        return NineRouterClient(base_url=llm.base_url, api_key=llm.api_key, model=model)
    return llm


def gate(record: DossierRecord, llm: Any, runtime: ProcessingRuntime, model: str | None) -> str | None:
    if not getattr(record, "content_sharing_consent", False):
        return "NO_CONSENT"
    if not runtime.egress_allowed:
        return "EGRESS_DENIED"
    client = classifier_client(llm, model) if llm is not None else None
    if client is None or not client.configured():
        return "LLM_UNAVAILABLE"
    if not model or not model.strip():
        return "MODEL_UNSET"
    if runtime.llm_calls_used >= runtime.max_llm_calls:
        return "BUDGET_EXHAUSTED"
    if runtime.remaining() < deadline_required(runtime):
        return "DEADLINE"
    return None


def build_pair_relations(
    record: DossierRecord, luong1_edges: Sequence[Any], *, llm: Any, runtime: ProcessingRuntime,
    sources: frozenset[PairSource] = ALL_SOURCES, top_k: int = PAIRS_TOP_K,
    model: str | None = None, candidates: PairCandidateSet | None = None,
    max_calls: int = PAIRS_MAX_CALLS,
) -> PairResult:
    model = os.getenv(PAIRS_MODEL_ENV) if model is None else model
    nodes = list(record.evidence_nodes())
    by_id = {n.node_id: n for n in nodes}
    index = StructureIndex.build(nodes, {s.file_id: s.role for s in record.source_files})
    excluded = frozenset(frozenset((edge.source_node_id, edge.target_node_id)) for edge in luong1_edges)
    candidate_set = candidates if candidates is not None else generate_pair_candidates(
        index, nodes, excluded_pairs=excluded, sources=sources, top_k=top_k,
    )
    candidate_stats = {"candidates_total": len(candidate_set.candidates),
                       "candidates_kept": len(candidate_set.candidates), "candidates_capped": 0,
                       "candidates_by_source": {}, "excluded_luong1": 0, "excluded_ancestor": 0,
                       "excluded_short": 0, "excluded_external_ref": 0}
    stats = {**candidate_stats, **candidate_set.stats, **classifier_stats(), "relations_total": 0,
             "relations_by_label": {label.value: 0 for label in PairLabel}}
    reason = gate(record, llm, runtime, model)
    if reason:
        stats["pairs_unclassified"] = len(candidate_set.candidates)
        stats["stopped_reason"] = reason
        return PairResult(mode="rule_only", rule_only_reason=reason, classifier_model=model,
                          prompt_version=PROMPT_VERSION, stats=stats)
    client = classifier_client(llm, model)
    pairs = [ClassifierPair(c, by_id[c.node_a].text or "", by_id[c.node_b].text or "",
                            clause_context(index, by_id, c.node_a), clause_context(index, by_id, c.node_b))
             for c in candidate_set.candidates]
    outcome = classify_pairs(pairs, client=client, runtime=runtime, max_calls=max_calls)
    stats.update(outcome.stats)
    verifier = CitationResolver(record.pages, record.tables, nodes)
    relations: dict[str, PairRelation] = {}
    digest = record.pins.source_snapshot_digest

    def citation(node_id: str, span: str) -> Citation | None:
        raw = citation_for_node(nodes, record.pages, node_id, text_span=span)
        if raw is None:
            return None
        result = Citation(**raw)
        # outline's legacy fallback may choose a wider span; it is not the requested quote.
        if result.text_span != span:
            return None
        result.validation_status = verifier.verify(result).status
        return result if result.validation_status == "VALID" else None

    for decision in outcome.decisions:
        a, b = decision.candidate.node_a, decision.candidate.node_b
        span_a, span_b = decision.span_a, decision.span_b
        directed = decision.label in {PairLabel.GENERAL_SPECIFIC, PairLabel.REFERENCE}
        if (directed and decision.direction == "B") or (not directed and index.position(a) > index.position(b)):
            a, b, span_a, span_b = b, a, span_b, span_a
        ca, cb = citation(a, span_a), citation(b, span_b)
        if ca is None or cb is None:
            stats["rejected"]["citation_invalid"] += 1
            continue
        relation_id = pair_relation_id_for(digest, decision.label, a, b)
        if relation_id in relations:
            continue
        relations[relation_id] = PairRelation(
            relation_id=relation_id, label=decision.label, node_a_id=a, node_b_id=b,
            directed=directed, candidate_sources=sorted(s.value for s in decision.candidate.sources),
            span_a=span_a, span_b=span_b, citation_a=ca, citation_b=cb,
            classifier_model=decision.served_model or model, prompt_version=PROMPT_VERSION,
            source_snapshot_digest=digest,
        )
        stats["relations_by_label"][decision.label.value] += 1
    stats["relations_total"] = len(relations)
    parts = {nid: index.part_of(nid) for r in relations.values() for nid in (r.node_a_id, r.node_b_id)}
    return PairResult(relations=list(relations.values()), mode="llm", classifier_model=stats["served_model"] or model,
                      prompt_version=PROMPT_VERSION, stats=stats, node_parts=parts,
                      batches_completed=outcome.batches_completed)
