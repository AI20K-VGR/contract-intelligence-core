from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from app.contracts.models import (
    Citation,
    EvidenceIssue,
    RelationEdge,
    RelationGraph,
    RelationNode,
    RelationSupport,
    RelationType,
    ReviewState,
)
from app.pipeline.citations import CitationResolver, quote_digest
from app.tools.store import DossierRecord

CLAUSE_RE = re.compile(r"(?:điều|dieu|article)\s+(\d+(?:\.\d+)?)", re.I)
ANNEX_RE = re.compile(r"(?:phụ lục|phu luc|annex)\s+(\d+)", re.I)
AMEND_RE = re.compile(r"(sửa|sua doi|amends?|điều chỉnh)", re.I)


def attach_ancestors(outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {n["node_id"]: n for n in outline}
    for n in outline:
        chain: list[str] = []
        cur = n.get("parent")
        guard = 0
        while cur and cur in by_id and guard < 20:
            chain.append(by_id[cur].get("raw_label") or "")
            cur = by_id[cur].get("parent")
            guard += 1
        n["ancestors"] = list(reversed(chain))
    return outline


def clause_key(label: str | None, text: str | None = None) -> str | None:
    blob = f"{label or ''} {text or ''}"
    m = CLAUSE_RE.search(blob)
    if not m:
        return None
    return f"Điều {m.group(1)}"


def doc_side(ancestors: list[str] | None, label: str | None) -> str:
    for heading in [*(ancestors or []), label or ""]:
        m = ANNEX_RE.match(heading.strip())
        if m:
            return f"Phụ lục {m.group(1)}"
        if re.fullmatch(r"phụ lục|phu luc|annex", heading.strip(), re.I):
            return "Phụ lục"
    return "Thân HĐ"


def related_node_ids(seed_ids: list[str], outline: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    by_id = {n["node_id"]: n for n in outline}
    seeds = [by_id[i] for i in seed_ids if i in by_id]
    keys = {clause_key(n.get("raw_label"), n.get("text")) for n in seeds}
    keys.discard(None)
    extra: list[str] = []
    rels: list[dict[str, Any]] = []
    seen_rel: set[tuple] = set()
    for n in outline:
        nid = n["node_id"]
        k = clause_key(n.get("raw_label"), n.get("text"))
        side = doc_side(n.get("ancestors"), n.get("raw_label"))
        blob = f"{n.get('raw_label') or ''} {n.get('text') or ''}"
        if k and k in keys:
            if nid not in seed_ids and nid not in extra:
                extra.append(nid)
            for s in seeds:
                sk = clause_key(s.get("raw_label"), s.get("text"))
                if sk != k or s["node_id"] == nid:
                    continue
                sig = ("SAME_CLAUSE", k, tuple(sorted([s["node_id"], nid])))
                if sig in seen_rel:
                    continue
                seen_rel.add(sig)
                rels.append(
                    {
                        "type": "SAME_CLAUSE",
                        "clause": k,
                        "left": s["node_id"],
                        "right": nid,
                        "left_side": doc_side(s.get("ancestors"), s.get("raw_label")),
                        "right_side": side,
                    }
                )
            if AMEND_RE.search(blob) and side != "Thân HĐ":
                rels.append({"type": "AMENDS", "clause": k, "from": nid, "side": side})
    return extra[:8], rels[:12]


def render_related_answer(packed: list[dict[str, Any]], rels: list[dict[str, Any]]) -> str:
    lines = ["Các đoạn liên quan trên thân HĐ và phụ lục (trích nguyên văn). Không suy ra điều nào thắng / thứ tự hiệu lực."]
    for n in packed:
        side = n.get("side") or ""
        path = n.get("path") or n.get("label") or n.get("node_id")
        text = (n.get("text") or "")[:400]
        lines.append(f"- [{side}] {path}: {text}")
    if rels:
        lines.append("Quan hệ:")
        for r in rels:
            if r.get("type") == "SAME_CLAUSE":
                lines.append(
                    f"- Cùng {r.get('clause')}: {r.get('left_side')} ({r.get('left')}) ↔ {r.get('right_side')} ({r.get('right')})"
                )
            elif r.get("type") == "AMENDS":
                lines.append(f"- {r.get('side')} có ngôn ngữ sửa/điều chỉnh {r.get('clause')} ({r.get('from')})")
    return "\n".join(lines)


_REFERENCE_PATTERNS = (
    ("ANNEX", re.compile("(?:ph\\u1ee5\\s+l\\u1ee5c|phu luc|annex)\\s+(\\d+)", re.I)),
    ("CLAUSE", re.compile("(?:\\u0111i\\u1ec1u|dieu|article)\\s+(\\d+(?:\\.\\d+)?)", re.I)),
)
_DEFINE_RE = re.compile(
    "(?:\\u0111\\u1ecbnh ngh\\u0129a|dinh nghia|defined as|c\\u00f3 ngh\\u0129a l\\u00e0|co nghia la|shall mean)"
    r"\\s*[:\\-]?\\s*[\\\"“]?([^\\\"”\\.;\\n]{2,100})",
    re.I,
)
_DEFINE_ASCII_RE = re.compile(r'(?:dinh nghia|defined as|co nghia la|shall mean)\s*[:\-]?\s*["“]?([^"”\.;\n]{2,100})', re.I)


def build_relation_graph(record: DossierRecord) -> RelationGraph:
    """Build a bounded, evidence-linked graph from one pinned snapshot."""

    digest = record.pins.source_snapshot_digest
    evidence_nodes = sorted(record.evidence_nodes(), key=lambda node: (node.order, node.node_id))
    graph_id = "graph:" + hashlib.sha256(
        f"{digest}|{','.join(node.node_id for node in evidence_nodes)}".encode("utf-8")
    ).hexdigest()[:24]
    source_roles = {source.file_id: source.role for source in record.source_files}
    graph_nodes = [
        RelationNode(
            node_id=node.node_id,
            node_kind="STRUCTURAL_NODE",
            source_file_id=node.source_file_id,
            source_role=source_roles.get(node.source_file_id or ""),
            page_range=list(node.page_range),
            page_revision_id=node.page_revision_id,
            quality=node.status,
        )
        for node in evidence_nodes
    ]
    by_id = {node.node_id: node for node in evidence_nodes}
    edges: list[RelationEdge] = []
    issues: list[EvidenceIssue] = []
    seen_edges: set[tuple[str, str, str]] = set()
    seen_issues: set[tuple[str, str, str, tuple[str, ...]]] = set()

    def citation(node_id: str, span: str | None = None) -> Citation:
        node = by_id[node_id]
        page = next((item for item in record.pages if item.page_revision_id == node.page_revision_id), None)
        if page is None:
            page = next(
                (
                    item
                    for item in record.pages
                    if node.source_file_id
                    and item.source_file_id == node.source_file_id
                    and item.page_in_file == (node.page_in_file or 1)
                ),
                None,
            )
        text_span = (span or node.text or node.raw_label or "")[:240]
        char_start = page.text.find(text_span) if page and text_span else -1
        citation = Citation(
            node_id=node_id,
            page_revision_id=node.page_revision_id or "",
            bbox=list(node.bbox),
            text_span=text_span,
            source_file_id=node.source_file_id,
            page=page.page_number if page else (node.page_range[0] if node.page_range else None),
            page_range=list(node.page_range),
            line_ids=list(node.source_line_ids),
            char_start=char_start if char_start >= 0 else None,
            char_end=(char_start + len(text_span)) if char_start >= 0 else None,
            source_hash=page.source_hash if page else None,
            quote_sha256=quote_digest(text_span),
            geometry_available=bool(node.bbox),
        )
        if page is not None:
            citation.validation_status = CitationResolver([page]).verify(citation).status
        return citation

    def add_edge(
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        support: RelationSupport,
        citations: list[Citation],
        state: ReviewState = ReviewState.NEEDS_REVIEW,
    ) -> None:
        key = (from_id, to_id, relation_type.value)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edge_id = "edge:" + hashlib.sha256(
            f"{digest}|{from_id}|{to_id}|{relation_type.value}".encode("utf-8")
        ).hexdigest()[:24]
        edges.append(
            RelationEdge(
                edge_id=edge_id,
                from_node_id=from_id,
                to_node_id=to_id,
                relation_type=relation_type,
                support=support,
                citations=citations,
                review_state=state,
                source_snapshot_digest=digest,
            )
        )

    for child in evidence_nodes:
        if not child.parent_id:
            continue
        if child.parent_id in by_id:
            add_edge(
                child.parent_id,
                child.node_id,
                RelationType.PARENT_OF,
                RelationSupport.STRUCTURAL,
                [citation(child.node_id)],
                ReviewState.PASS,
            )
        else:
            issues.append(
                _graph_issue(
                    digest,
                    f"missing parent {child.parent_id}",
                    citation(child.node_id),
                )
            )

    clause_groups: dict[str, list[str]] = {}
    for node in evidence_nodes:
        key = _robust_clause_key(node.raw_label, node.text)
        if key:
            clause_groups.setdefault(key, []).append(node.node_id)
    for node_ids in clause_groups.values():
        for left_index, left_id in enumerate(node_ids):
            for right_id in node_ids[left_index + 1 :]:
                left = by_id[left_id]
                right = by_id[right_id]
                if left.source_file_id == right.source_file_id:
                    continue
                add_edge(
                    left_id,
                    right_id,
                    RelationType.SAME_CLAUSE,
                    RelationSupport.HEURISTIC,
                    [citation(left_id), citation(right_id)],
                )

    for node in evidence_nodes:
        blob = f"{node.raw_label}\n{node.text}"
        for kind, pattern in _REFERENCE_PATTERNS:
            for match in pattern.finditer(blob):
                if _is_heading_reference(node, match.group(0)):
                    continue
                targets = _resolve_reference(kind, match.group(1), node, evidence_nodes)
                if len(targets) == 1:
                    target_id = targets[0]
                    refs = [citation(node.node_id, match.group(0)), citation(target_id)]
                    add_edge(node.node_id, target_id, RelationType.REFERENCES, RelationSupport.EXPLICIT_TEXT, refs)
                    if _has_amend_marker(blob) and kind == "CLAUSE":
                        add_edge(node.node_id, target_id, RelationType.AMENDS, RelationSupport.EXPLICIT_TEXT, refs)
                elif not targets:
                    issues.append(_graph_issue(digest, f"missing {kind.lower()} {match.group(1)}", citation(node.node_id, match.group(0))))
                else:
                    issue_citation = citation(node.node_id, match.group(0))
                    issue_key = (
                        kind,
                        match.group(1),
                        issue_citation.page_revision_id,
                        tuple(issue_citation.line_ids),
                    )
                    if issue_key not in seen_issues:
                        seen_issues.add(issue_key)
                        issues.append(_graph_issue(digest, f"ambiguous {kind.lower()} {match.group(1)}", issue_citation))

    for definition in evidence_nodes:
        definition_blob = f"{definition.raw_label}\n{definition.text}"
        match = _DEFINE_RE.search(definition_blob) or _DEFINE_ASCII_RE.search(_normalize_relation_text(definition_blob))
        if not match:
            continue
        term = match.group(1).strip(" \\t\\\"“”'()")
        term_id = "term:" + hashlib.sha256(
            f"{digest}|{definition.node_id}|{term.casefold()}".encode("utf-8")
        ).hexdigest()[:24]
        if not any(node.node_id == term_id for node in graph_nodes):
            graph_nodes.append(
                RelationNode(
                    node_id=term_id,
                    node_kind="DEFINED_TERM",
                    source_file_id=definition.source_file_id,
                    source_role=source_roles.get(definition.source_file_id or ""),
                    page_range=list(definition.page_range),
                    page_revision_id=definition.page_revision_id,
                    quality=definition.status,
                )
            )
        add_edge(
            definition.node_id,
            term_id,
            RelationType.DEFINES,
            RelationSupport.EXPLICIT_TEXT,
            [citation(definition.node_id, definition.text or definition.raw_label)],
        )
        normalized_term = _normalize_relation_text(term)
        for usage in evidence_nodes:
            if usage.node_id != definition.node_id and normalized_term in _normalize_relation_text(usage.text):
                add_edge(
                    term_id,
                    usage.node_id,
                    RelationType.USES_DEFINED_TERM,
                    RelationSupport.HEURISTIC,
                    [citation(definition.node_id, definition.text or definition.raw_label), citation(usage.node_id, term)],
                )

    return RelationGraph(
        graph_id=graph_id,
        source_snapshot_digest=digest,
        nodes=graph_nodes,
        edges=edges,
        issues=issues,
    )


def _robust_clause_key(label: str | None, text: str | None = None) -> str | None:
    normalized = _normalize_relation_text(f"{label or ''} {text or ''}")
    match = re.search(r"(?:dieu|article)\s+(\d+(?:\.\d+)?)", normalized, re.I)
    return f"dieu {match.group(1)}" if match else None


def _normalize_relation_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d").replace("Ä‘", "d")


def _resolve_reference(kind: str, value: str, source: Any, nodes: list[Any]) -> list[str]:
    if kind == "CLAUSE":
        key = f"dieu {value}"
        return [node.node_id for node in nodes if _robust_clause_key(node.raw_label, node.text) == key and node.node_id != source.node_id]
    needle = _normalize_relation_text(f"phu luc {value}")
    candidates = [
        node.node_id
        for node in nodes
        if node.node_id != source.node_id
        and node.type != "FIELD"
        and needle in _normalize_relation_text(f"{node.raw_label} {node.text}")
    ]
    if len(candidates) <= 1:
        return candidates
    primary = []
    for node in nodes:
        if node.node_id not in candidates:
            continue
        label = _normalize_relation_text(node.raw_label or "").strip()
        if re.match(rf"^phu\s+luc\s+{re.escape(value)}\b", label) and not re.search(r"\b(tiep\s+theo|continued|continue)\b", label):
            primary.append(node.node_id)
    return primary if len(primary) == 1 else candidates


def _graph_issue(digest: str, missing: str, citation: Citation) -> EvidenceIssue:
    issue_id = "graph-issue:" + hashlib.sha256(
        f"{digest}|{missing}|{citation.node_id}|{citation.text_span}".encode("utf-8")
    ).hexdigest()[:24]
    return EvidenceIssue(
        issue_id=issue_id,
        missing=missing,
        reason=f"Không resolve được quan hệ: {missing}; không suy đoán target.",
        citation=citation,
        review_state=ReviewState.INSUFFICIENT_EVIDENCE,
    )


def _has_amend_marker(value: str) -> bool:
    normalized = _normalize_relation_text(value)
    return bool(AMEND_RE.search(value) or re.search(r"(?:sua|thay the|dieu chinh|amend)", normalized, re.I))


def _is_heading_reference(node: Any, reference: str) -> bool:
    """Do not treat a node's own title as an explicit cross-reference."""
    ref = _normalize_relation_text(reference).strip()
    label = _normalize_relation_text(node.raw_label or "").strip()
    text = _normalize_relation_text(node.text or "").strip()
    return bool(ref and ((label == ref) or text.startswith(ref)))
