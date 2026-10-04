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
    """The clause this node *is*, not a clause it merely mentions."""

    for source in (label, text):
        normalized = _normalize_relation_text((source or "").strip())
        match = re.match(r"(?:dieu|article)\s+(\d+(?:\.\d+)?)", normalized, re.I)
        if match:
            return f"Điều {match.group(1)}"
    return None


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
            clause_number = re.search(r"\d+(?:\.\d+)?", k)
            if (
                clause_number
                and side != "Thân HĐ"
                and _explicit_amend_reference(blob, clause_number.group(0))
            ):
                rels.append({"type": "AMENDS", "clause": k, "from": nid, "side": side})
    return extra[:8], rels[:12]


_CROSS_RELATIONS = {
    RelationType.SAME_CLAUSE,
    RelationType.REFERENCES,
    RelationType.AMENDS,
    RelationType.DEFINES,
}
_RELATION_PHRASE = {
    RelationType.SAME_CLAUSE: "cùng số điều",
    RelationType.REFERENCES: "dẫn chiếu",
    RelationType.AMENDS: "có ngôn ngữ sửa",
    RelationType.DEFINES: "định nghĩa",
}


def _member_side(record: DossierRecord, node_id: str) -> str:
    by_id = {node.node_id: node for node in record.evidence_nodes()}
    node = by_id.get(node_id)
    if node is None:
        return ""
    file_role = {item.file_id: item.role for item in record.source_files}.get(node.source_file_id or "")
    if file_role in {"body", "annex"}:
        return file_role
    labels: list[str] = []
    current = node
    guard = 0
    while current is not None and guard < 12:
        labels.append(current.raw_label or "")
        current = by_id.get(current.parent_id) if current.parent_id else None
        guard += 1
    blob = _normalize_relation_text(" ".join(labels))
    if re.search(r"\bphu luc\b|\bannex\b", blob):
        return "annex"
    return "body"


def render_same_item_relations(record: DossierRecord) -> dict[str, Any] | None:
    """One sentence per item. Body values stay on the body; annex values stay on the annex."""

    grouped: dict[str, list] = {}
    for fact in record.facts:
        key = str(fact.item_key or "")
        if not key or key.startswith("party_") or key.startswith("mst_party_"):
            continue
        grouped.setdefault(key, []).append(fact)
    lines = [
        "Mỗi mục dưới đây chỉ ghép cùng một hạng mục giữa hợp đồng và phụ lục. Hai hạng mục khác nhau không bị gộp. Máy không kết luận bên nào có hiệu lực.",
    ]
    citations: list[dict[str, Any]] = []
    wrote = False
    for key in sorted(grouped):
        facts = grouped[key]
        bodies = [fact for fact in facts if fact.source_role != "annex"]
        annexes = [fact for fact in facts if fact.source_role == "annex"]
        if not bodies or not annexes:
            continue
        wrote = True
        label = _item_label(key)
        body_bits = [_value_phrase(fact) for fact in _unique_fact_values(bodies)]
        annex_bits = [_value_phrase(fact) for fact in _unique_fact_values(annexes)]
        currencies = {fact.currency for fact in [*bodies, *annexes] if fact.currency}
        sentence = f"Cùng {label}: trên hợp đồng là {'; '.join(body_bits)}; trên phụ lục là {'; '.join(annex_bits)}."
        when = _effective_when(annexes) or _effective_when(bodies)
        if when:
            sentence += f" Mốc ghi trên văn bản: {when}."
        else:
            sentence += " Không thấy ngày bắt đầu áp dụng trên đoạn đã trích."
        if len(currencies) > 1:
            sentence += " Hai bên khác tiền tệ, không quy đổi."
        lines.append(sentence)
        for fact in [*bodies, *annexes]:
            if fact.citation and fact.citation.node_id:
                citations.append({
                    "node_id": fact.citation.node_id,
                    "text_span": (fact.citation.text_span or fact.raw_value)[:200],
                })
    if not wrote:
        return None
    return {
        "review_state": ReviewState.NEEDS_REVIEW.value,
        "answer": "\n".join(lines),
        "citations": citations[:8],
        "notes": "same_item_relation",
    }


def _item_label(key: str) -> str:
    names = {
        "contract_value": "giá hợp đồng",
        "penalty_general": "phạt chậm chung",
        "penalty_construction": "phạt phần xây lắp",
        "penalty_equipment": "phạt phần thiết bị",
        "penalty_lt10": "phạt khi chậm dưới 10 ngày",
        "penalty_gte10": "phạt khi chậm từ 10 ngày",
        "price_usd": "đơn giá thiết bị nhập",
    }
    if key in names:
        return names[key]
    if len(key) <= 3:
        return f"hạng mục {key}"
    return key.replace("_", " ")


def _unique_fact_values(facts: list) -> list:
    seen: set[str] = set()
    out = []
    for fact in facts:
        marker = str(fact.normalized_value or fact.raw_value)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(fact)
    return out


def _value_phrase(fact) -> str:
    number = _grouped_amount(fact.normalized_value or fact.raw_value)
    if fact.currency:
        shown = f"{number} {fact.currency}"
    else:
        raw = fact.raw_value or ""
        shown = f"{number}%" if "%" in raw and "%" not in str(number) else str(number)
    span = (fact.citation.text_span if fact.citation else "") or ""
    folded = span.casefold()
    if "bảng tóm tắt" in folded or "bang tom tat" in folded:
        shown += " (bảng tóm tắt trên hợp đồng)"
    return shown


def _grouped_amount(value) -> str:
    text = str(value or "")
    if not text.isdigit() or len(text) <= 3:
        return text
    parts: list[str] = []
    while text:
        parts.append(text[-3:])
        text = text[:-3]
    return ".".join(reversed(parts))


def _effective_when(facts: list) -> str | None:
    for fact in facts:
        if fact.period_start:
            return f"kể từ {fact.period_start}"
        text = fact.citation.text_span if fact.citation else ""
        match = re.search(
            r"(?:kể từ|ke tu|từ ngày|tu ngay)\s+(\d{1,2}/\d{1,2}/\d{2,4})",
            text or "",
            re.I,
        )
        if match:
            return f"kể từ {match.group(1)}"
    return None


def render_relation_verdict(record: DossierRecord) -> dict[str, Any]:
    """Say which annex clauses touch the contract. Do not dump node JSON."""

    body_clauses: dict[str, Any] = {}
    annex_clauses: dict[str, Any] = {}
    for node in record.evidence_nodes():
        if node.type != "CLAUSE":
            continue
        number = _clause_number(node.raw_label, node.text)
        if not number:
            continue
        side = _member_side(record, node.node_id)
        target = annex_clauses if side == "annex" else body_clauses
        target.setdefault(number, node)

    shared = sorted(set(body_clauses) & set(annex_clauses), key=int)
    if not shared:
        return {
            "review_state": ReviewState.INSUFFICIENT_EVIDENCE.value,
            "answer": "Không thấy điều nào của phụ lục trùng số với hợp đồng. Không suy ra là hai văn bản không liên quan.",
            "citations": [],
            "notes": "relation_absent",
        }

    lines = [
        "Phụ lục gắn với hợp đồng ở các điều cùng số dưới đây. Phụ lục có chữ sửa thì đó là chỗ nó viết lại điều của hợp đồng. Máy không kết luận điều nào có hiệu lực.",
    ]
    citations: list[dict[str, Any]] = []
    for number in shared:
        body = body_clauses[number]
        annex = annex_clauses[number]
        annex_label = _short_clause_title(annex.raw_label)
        body_label = _short_clause_title(body.raw_label)
        amended = bool(re.search(r"sửa|sua|thay", _normalize_relation_text(annex.raw_label or ""), re.I))
        action = "phụ lục có chữ sửa điều này" if amended else "cùng số điều, phụ lục không ghi chữ sửa"
        lines.append(f"- Điều {number}: thân «{body_label}»; phụ lục «{annex_label}» — {action}.")
        for node in (body, annex):
            citations.append({
                "node_id": node.node_id,
                "text_span": (node.raw_label or "")[:160],
            })
    return {
        "review_state": ReviewState.NEEDS_REVIEW.value,
        "answer": "\n".join(lines),
        "citations": citations[:8],
        "notes": "relation_verdict",
    }


def _clause_number(label: str | None, text: str | None) -> str | None:
    match = re.search(r"dieu\s+(\d+)", _normalize_relation_text(f"{label or ''} {text or ''}"))
    return match.group(1) if match else None


def _short_clause_title(label: str | None) -> str:
    text = re.sub(r"^\s*Điều\s+\d+\.?\s*", "", label or "", flags=re.I).strip()
    return text[:80] or (label or "không có tiêu đề")


def render_related_answer(packed: list[dict[str, Any]], rels: list[dict[str, Any]]) -> str:
    lines = ["Các đoạn liên quan trên thân HĐ và phụ lục (trích nguyên văn). Không suy ra điều nào thắng / thứ tự hiệu lực."]
    for n in packed:
        side = n.get("side") or ""
        path = n.get("path") or n.get("label") or n.get("node_id")
        text = (n.get("text") or "").strip()
        label = (n.get("label") or "").strip()
        if text and text not in (path or "") and text != label:
            lines.append(f"- [{side}] {path}: {text[:400]}")
        else:
            lines.append(f"- [{side}] {path}")
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
                    if _explicit_amend_reference(blob, match.group(1)) and kind == "CLAUSE":
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
    """Identity of a clause heading. A later mention of another article is not that clause."""

    for source in (label, text):
        normalized = _normalize_relation_text((source or "").strip())
        match = re.match(r"(?:dieu|article)\s+(\d+(?:\.\d+)?)", normalized, re.I)
        if match:
            return f"dieu {match.group(1)}"
    return None


def _annex_numbers(text: str) -> set[int]:
    normalized = _normalize_relation_text(text)
    return {int(number) for number in re.findall(r"phu luc\s+0*(\d+)\b", normalized)}


def _normalize_relation_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d").replace("Ä‘", "d")


def _resolve_reference(kind: str, value: str, source: Any, nodes: list[Any]) -> list[str]:
    if kind == "CLAUSE":
        key = f"dieu {value}"
        return [node.node_id for node in nodes if _robust_clause_key(node.raw_label, node.text) == key and node.node_id != source.node_id]
    needle = _normalize_relation_text(f"phu luc {value}")
    wanted = int(value) if str(value).isdigit() else None
    candidates = []
    for node in nodes:
        if node.node_id == source.node_id or node.type == "FIELD":
            continue
        blob = _normalize_relation_text(f"{node.raw_label} {node.text}")
        if wanted is not None and wanted in _annex_numbers(blob):
            candidates.append(node.node_id)
        elif wanted is None and needle in blob:
            candidates.append(node.node_id)
    if len(candidates) <= 1:
        return candidates
    primary = []
    for node in nodes:
        if node.node_id not in candidates:
            continue
        label = _normalize_relation_text(node.raw_label or "").strip()
        if wanted is not None and re.match(rf"^phu\s+luc\s+0*{wanted}\b", label) and not re.search(
            r"\b(tiep\s+theo|continued|continue)\b", label
        ):
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


def _explicit_amend_reference(value: str, target_number: str) -> bool:
    """Require a specific amendment marker tied to the referenced clause."""
    normalized = _normalize_relation_text(value)
    number = re.escape(str(int(target_number))) if str(target_number).isdigit() else re.escape(target_number)
    marker = r"(?:sua doi|thay the|dieu chinh|amends?)"
    target = rf"(?:dieu|article)\s+0*{number}\b"
    return bool(
        re.search(rf"{marker}\s+(?:noi dung\s+)?{target}", normalized, re.I)
        or re.search(rf"{target}[^.;\n]{{0,80}}{marker}", normalized, re.I)
    )


def _is_heading_reference(node: Any, reference: str) -> bool:
    """Do not treat a node's own title as an explicit cross-reference."""
    ref = _normalize_relation_text(reference).strip()
    label = _normalize_relation_text(node.raw_label or "").strip()
    text = _normalize_relation_text(node.text or "").strip()
    return bool(ref and ((label == ref) or text.startswith(ref)))
