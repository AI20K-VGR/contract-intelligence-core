"""Project grounded pair proposals onto existing review findings and coverage."""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from app.contracts.contract_graph import PairLabel, PairResult
from app.contracts.models import (
    Candidate,
    Citation,
    ComparisonScope,
    Disposition,
    EvidenceIssue,
    FindingType,
    ModelDisposition,
    ReviewState,
)
from app.pipeline.citations import CitationResolver
from app.pipeline.contract_graph.projection import _candidate_pair
from app.pipeline.contract_graph.resolver import StructureIndex
from app.pipeline.outline import citation_for_node
from app.tools.store import DossierRecord

PAIRS_MAX_CONFLICT_FINDINGS = 5
_CONFLICT_REASON = (
    "AI2 gợi ý hai khoản có thể quy định khác nhau cho cùng một nội dung "
    "(mô hình ngôn ngữ đề xuất, trích dẫn đã được kiểm); cần người duyệt đối chiếu, "
    "AI2 không kết luận khoản nào được áp dụng."
)
_LIMITED_REASONS = {
    "NO_CONSENT": "Chưa có đồng ý chia sẻ nội dung hợp đồng cho mô hình ngôn ngữ",
    "EGRESS_DENIED": "Chính sách vận hành không cho phép gửi nội dung ra mô hình ngôn ngữ",
    "LLM_UNAVAILABLE": "Mô hình ngôn ngữ chưa sẵn sàng",
    "MODEL_UNSET": "Chưa cấu hình mô hình phân loại khoản",
    "BUDGET_EXHAUSTED": "Ngân sách gọi mô hình ngôn ngữ đã hết",
    "DEADLINE": "Thời gian còn lại không đủ để phân tích quan hệ",
}
_COUNTS = (
    "candidates_total", "candidates_kept", "candidates_capped", "excluded_luong1",
    "excluded_external_ref", "pairs_sent", "pairs_unclassified", "llm_calls", "prompt_tokens",
    "completion_tokens", "injection_signals",
)
_CONFLICT_COUNTS = (
    "conflict_findings", "conflict_capped", "conflict_deduped_with_candidates",
    "conflict_citation_invalid",
)


def _scope(a: str, b: str) -> ComparisonScope:
    if a.startswith("body:") and b.startswith("body:"):
        return ComparisonScope.WITHIN_DOCUMENT
    if a.startswith("annex:") and b.startswith("annex:"):
        return ComparisonScope.ANNEX_ANNEX
    return ComparisonScope.CONTRACT_ANNEX


def pair_conflict_candidates(
    result: PairResult, candidates: Sequence[Candidate], record: DossierRecord,
) -> tuple[list[Candidate], dict[str, int]]:
    stats = dict.fromkeys(_CONFLICT_COUNTS, 0)
    existing = {pair for c in candidates if (pair := _candidate_pair(c)) is not None}
    nodes = record.evidence_nodes()
    by_id = {node.node_id: node for node in nodes}
    index = StructureIndex.build(nodes, {s.file_id: s.role for s in record.source_files})
    resolver = CitationResolver(record.pages, record.tables, nodes)
    output: list[Candidate] = []
    for relation in result.relations:
        if relation.label != PairLabel.CONFLICT:
            continue
        a, b = relation.node_a_id, relation.node_b_id
        pair = tuple(sorted((a, b)))
        if pair in existing:
            stats["conflict_deduped_with_candidates"] += 1
            continue
        if len(output) >= PAIRS_MAX_CONFLICT_FINDINGS:
            stats["conflict_capped"] += 1
            continue
        citations = []
        for node_id in (a, b):
            node = by_id.get(node_id)
            if node is None or not node.text:
                break
            # Legacy default truncates at 240 chars; a pairs finding must retain the full node.
            raw = citation_for_node(nodes, record.pages, node_id, text_span=node.text)
            if raw is None or raw.get("text_span") != node.text:
                break
            citation = Citation(**raw)
            citation.validation_status = resolver.verify(citation).status
            if citation.validation_status != "VALID":
                break
            citations.append(citation)
        if len(citations) != 2:
            stats["conflict_citation_invalid"] += 1
            continue
        ca, cb = index.canonical_of(a), index.canonical_of(b)
        digest = hashlib.sha256(f"{record.pins.source_snapshot_digest}|{a}|{b}".encode()).hexdigest()[:12]
        output.append(Candidate(
            candidate_id="cand_pair_" + digest, left_id=a, right_id=b,
            finding_type=FindingType.COMPARABLE_DIFFERENCE, model_disposition=ModelDisposition.UNCLEAR,
            review_state=ReviewState.NEEDS_REVIEW, evidence_left=[citations[0]], evidence_right=[citations[1]],
            reason=_CONFLICT_REASON, disposition=Disposition.COMPARABLE_DIFFERENCE,
            scope=_scope(result.node_parts.get(a, "body:"), result.node_parts.get(b, "body:")),
            item_key=f"{ca} ↔ {cb}" if ca and cb else None,
        ))
        existing.add(pair)
    stats["conflict_findings"] = len(output)
    return output, stats


def limited_coverage_issue(result: PairResult) -> EvidenceIssue:
    reason = _LIMITED_REASONS.get(result.rule_only_reason, "Chưa phân tích được quan hệ ngầm")
    count = result.stats.get("candidates_kept", 0)
    return EvidenceIssue(
        issue_id="contract-graph:CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE",
        missing="CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE", review_state=ReviewState.NEEDS_REVIEW,
        reason=f"{reason}; quan hệ ngầm giữa các khoản chưa được phân tích ({count} cặp ứng viên). "
               "Không có phát hiện không có nghĩa là không có rủi ro.",
    )


def pair_coverage(
    result: PairResult | None, *, status: str, conflict_stats: dict[str, int],
) -> dict[str, Any]:
    active = result if status == "OK" else None
    stats = active.stats if active else {}
    pairs = {"status": status, "mode": active.mode if active else None,
             "rule_only_reason": active.rule_only_reason if active else None,
             "classifier_model": active.classifier_model if active else None,
             "prompt_version": active.prompt_version if active else None,
             **{key: stats.get(key, 0) for key in _COUNTS},
             "candidates_by_source": stats.get("candidates_by_source", {}),
             "relations_total": len(active.relations) if active else 0,
             "relations_by_label": {label.value: sum(r.label == label for r in active.relations)
                                    if active else 0 for label in PairLabel},
             "rejected": stats.get("rejected", {}), "stopped_reason": stats.get("stopped_reason"),
             "batches_completed": active.batches_completed if active else 0,
             **{key: conflict_stats.get(key, 0) if active else 0 for key in _CONFLICT_COUNTS}}
    return {"graph_mode": "operation_first+pairs_" + active.mode if active else "operation_first",
            "pairs": pairs}
