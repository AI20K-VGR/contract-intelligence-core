"""Build a bounded, evidence-linked context view for one contract document.

This layer deliberately does not merge independent contracts.  It only
classifies body/annex parts that occur inside the same immutable snapshot and
turns explicit links, amendment language, and comparison candidates into
reviewable signals.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Iterable

from app.contracts.models import (
    Candidate,
    Citation,
    ContextFinding,
    ContractContext,
    ContractPart,
    Disposition,
    Fact,
    RelationType,
    ReviewState,
)
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.citations import quote_digest
from app.pipeline.citations import CitationResolver
from app.tools.store import DossierRecord


ANNEX_HEADING_RE = re.compile(r"^\s*phu\s+luc\s+(?:so\s*)?(\d+)\b", re.I)
ANNEX_MENTION_RE = re.compile(r"\bphu\s+luc\s+(?:so\s*)?(\d+)\b", re.I)
AMENDMENT_RE = re.compile(r"\b(?:sua\s+doi|thay\s+the|dieu\s+chinh|bo\s+sung|cap\s+nhat|amend)\b", re.I)
CLAUSE_RE = re.compile(r"\bdieu\s+(\d+(?:\.\d+)?)\b", re.I)
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")


def build_contract_context(
    record: DossierRecord,
    *,
    candidates: Iterable[Candidate] = (),
    facts: Iterable[Fact] = (),
) -> ContractContext:
    """Return the context inventory for one ``DossierRecord``.

    Annex detection is conservative: only a page whose line starts with a
    normalized ``PHỤ LỤC <n>`` heading opens an annex range.  A casual mention
    of an appendix in a clause never reclassifies the rest of the contract.
    """

    digest = record.pins.source_snapshot_digest
    annex_ranges = _annex_ranges(record)
    parts: list[ContractPart] = []
    body_ids: list[str] = []
    body_pages: set[int] = set()
    annex_ids: dict[str, list[str]] = defaultdict(list)
    annex_pages: dict[str, set[int]] = defaultdict(set)

    for node in sorted(record.evidence_nodes(), key=lambda item: (item.order, item.node_id)):
        matching = [number for number, pages in annex_ranges.items() if set(node.page_range).intersection(pages)]
        if matching:
            number = matching[0]
            annex_ids[number].append(node.node_id)
            annex_pages[number].update(page for page in node.page_range if page in annex_ranges[number])
        else:
            body_ids.append(node.node_id)
            body_pages.update(node.page_range)

    if body_ids or body_pages:
        parts.append(
            ContractPart(
                part_id="body",
                kind="BODY",
                label="Thân hợp đồng",
                node_ids=body_ids,
                page_range=sorted(body_pages),
                citation=_page_citation(record, min(body_pages) if body_pages else None),
                confidence=1.0,
            )
        )
    for number in sorted(annex_ids, key=_number_sort):
        pages = sorted(annex_pages[number])
        parts.append(
            ContractPart(
                part_id=f"annex:{number}",
                kind="ANNEX",
                label=f"Phụ lục {number}",
                annex_number=number,
                node_ids=annex_ids[number],
                page_range=pages,
                citation=_page_citation(record, pages[0] if pages else None),
                confidence=0.98,
            )
        )

    if not parts:
        parts.append(ContractPart(part_id="unknown", kind="UNKNOWN", label="Không xác định", confidence=0.0))

    node_part = {node_id: part.part_id for part in parts for node_id in part.node_ids}
    findings: list[ContextFinding] = []

    for part in parts:
        if part.kind != "ANNEX":
            continue
        number = part.annex_number or ""
        body_refs = _body_annex_references(record, body_ids, number)
        annex_refs_contract = _annex_contract_reference(record, part.node_ids)
        if body_refs or annex_refs_contract:
            link_nodes = [*body_refs, *annex_refs_contract, *part.node_ids[:1]]
            if not body_refs and body_ids:
                link_nodes.insert(0, body_ids[0])
            findings.append(
                _finding(
                    digest,
                    "PART_LINK",
                    f"annex:{number}",
                    link_nodes,
                    f"Phụ lục {number} có căn cứ gắn với hợp đồng trong cùng snapshot; chưa kết luận hiệu lực pháp lý hay thứ tự ưu tiên.",
                    ReviewState.PASS,
                    RelationType.REFERENCES,
                    _node_citations(record, link_nodes),
                )
            )
        else:
            findings.append(
                _finding(
                    digest,
                    "CONTEXT_GAP",
                    f"annex:{number}",
                    part.node_ids[:1],
                    f"Phát hiện Phụ lục {number} nhưng chưa thấy tham chiếu rõ từ thân hợp đồng; cần kiểm tra số phụ lục và căn cứ gắn kèm.",
                    ReviewState.NEEDS_REVIEW,
                    None,
                    _node_citations(record, part.node_ids[:1]),
                )
            )

        annex_text = "\n".join(_node_text(record, node_id) for node_id in part.node_ids)
        if AMENDMENT_RE.search(fold_for_match(annex_text)):
            clauses = sorted({match.group(1) for match in CLAUSE_RE.finditer(fold_for_match(annex_text))})
            dates = sorted({match.group(0) for match in DATE_RE.finditer(annex_text)})
            findings.append(
                _finding(
                    digest,
                    "AMENDMENT_SIGNAL",
                    f"annex:{number}",
                    part.node_ids,
                    f"Phụ lục {number} có ngôn ngữ sửa đổi/bổ sung/thay thế; AI2 chỉ phát hiện tín hiệu và yêu cầu đối chiếu điều khoản đích.",
                    ReviewState.NEEDS_REVIEW,
                    RelationType.AMENDS,
                    _node_citations(record, part.node_ids[:4]),
                    metadata={"clause_signals": clauses, "date_signals": dates},
                )
            )

    for candidate in candidates:
        source_ids = [
            *[citation.node_id for citation in candidate.evidence_left if citation.node_id],
            *[citation.node_id for citation in candidate.evidence_right if citation.node_id],
        ]
        distinct_parts = {node_part.get(node_id) for node_id in source_ids if node_part.get(node_id)}
        if len(distinct_parts) < 2:
            continue
        if candidate.disposition == Disposition.COMPARABLE_MATCH:
            continue
        findings.append(
            _finding(
                digest,
                "CONTEXT_CONFLICT",
                candidate.item_key,
                source_ids,
                "Hai nguồn trong cùng hợp đồng có giá trị/ngữ cảnh khác nhau; cần xem điều khoản sửa đổi và hiệu lực, AI2 không chọn bên thắng.",
                candidate.review_state,
                RelationType.AMENDS if candidate.disposition == Disposition.CANDIDATE_AMENDMENT else None,
                [*candidate.evidence_left, *candidate.evidence_right],
                metadata={"candidate_id": candidate.candidate_id, "disposition": candidate.disposition.value if candidate.disposition else None},
            )
        )

    facts_by_item: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        if fact.item_key and fact.source_role == "annex":
            facts_by_item[fact.item_key].append(fact)
    for item_key, item_facts in facts_by_item.items():
        values = {fact.normalized_value or fact.raw_value for fact in item_facts}
        part_ids = {
            node_part.get(fact.citation.node_id)
            for fact in item_facts
            if node_part.get(fact.citation.node_id)
        }
        if len(values) < 2 or len(part_ids) < 2:
            continue
        periods = sorted({fact.period_start for fact in item_facts if fact.period_start})
        citations = [fact.citation for fact in item_facts]
        findings.append(
            _finding(
                digest,
                "CONTEXT_CONFLICT",
                item_key,
                [fact.citation.node_id for fact in item_facts],
                "Các phụ lục trong cùng hợp đồng có giá trị khác nhau; có thể là các phiên bản theo thời điểm hoặc xung đột, cần đối chiếu điều khoản hiệu lực.",
                ReviewState.NEEDS_REVIEW,
                None,
                citations,
                metadata={"values": sorted(values), "periods": periods, "part_ids": sorted(part_ids)},
            )
        )

    resolver = CitationResolver(record.pages, record.tables, record.evidence_nodes())
    for finding in findings:
        statuses = [resolver.verify(citation).status for citation in finding.citations]
        if finding.review_state == ReviewState.PASS and (
            not statuses or any(status != "VALID" for status in statuses)
        ):
            finding.review_state = ReviewState.NEEDS_REVIEW
            finding.metadata["citation_verification"] = statuses or ["MISSING"]

    return ContractContext(
        context_id="context:" + hashlib.sha256(f"{digest}|{','.join(p.part_id for p in parts)}".encode("utf-8")).hexdigest()[:24],
        source_file_ids=sorted({node.source_file_id for node in record.evidence_nodes() if node.source_file_id}),
        parts=parts,
        findings=findings,
    )


def _annex_ranges(record: DossierRecord) -> dict[str, set[int]]:
    markers: list[tuple[int, str]] = []
    for page in sorted(record.pages, key=lambda item: item.page_number):
        lines = list(page.line_texts.values())
        for line in lines or [page.text.splitlines()[0] if page.text else ""]:
            match = ANNEX_HEADING_RE.match(fold_for_match(line))
            if match:
                markers.append((page.page_number, match.group(1)))
                break
    first_markers: dict[str, int] = {}
    for page_number, number in markers:
        first_markers[number] = min(page_number, first_markers.get(number, page_number))
    unique_markers = sorted((page_number, number) for number, page_number in first_markers.items())
    result: dict[str, set[int]] = {}
    for index, (start, number) in enumerate(unique_markers):
        end = unique_markers[index + 1][0] - 1 if index + 1 < len(unique_markers) else max((p.page_number for p in record.pages), default=start)
        result[number] = set(range(start, end + 1))
    return result


def _body_annex_references(record: DossierRecord, body_ids: list[str], number: str) -> list[str]:
    refs: list[str] = []
    for node_id in body_ids:
        text = fold_for_match(_node_text(record, node_id))
        if "phu luc" in text and (not number or number in {match.group(1) for match in ANNEX_MENTION_RE.finditer(text)}):
            refs.append(node_id)
    return refs


def _annex_contract_reference(record: DossierRecord, annex_ids: list[str]) -> list[str]:
    refs: list[str] = []
    for node_id in annex_ids:
        text = fold_for_match(_node_text(record, node_id))
        if "hop dong" in text and ("kem theo" in text or "so " in text):
            refs.append(node_id)
    return refs


def _node_text(record: DossierRecord, node_id: str) -> str:
    node = next((item for item in record.evidence_nodes() if item.node_id == node_id), None)
    return f"{node.raw_label}\n{node.text}" if node else ""


def _node_citations(record: DossierRecord, node_ids: list[str]) -> list[Citation]:
    resolver = CitationResolver(record.pages, record.tables, record.evidence_nodes())
    citations: list[Citation] = []
    for node_id in node_ids:
        citation = _node_citation(record, node_id)
        if citation is not None and resolver.verify(citation).valid:
            citations.append(citation)
    return citations


def _node_citation(record: DossierRecord, node_id: str) -> Citation | None:
    node = next((item for item in record.evidence_nodes() if item.node_id == node_id), None)
    if node is None:
        return None
    page = next((item for item in record.pages if item.page_revision_id == node.page_revision_id), None)
    text = (node.text or node.raw_label or "")[:240]
    char_start = page.text.find(text) if page and text else -1
    return Citation(
        node_id=node_id,
        page_revision_id=node.page_revision_id or "",
        bbox=list(node.bbox),
        text_span=text,
        source_file_id=node.source_file_id,
        page=page.page_number if page else (node.page_range[0] if node.page_range else None),
        page_range=list(node.page_range),
        line_ids=list(node.source_line_ids),
        char_start=char_start if char_start >= 0 else None,
        char_end=(char_start + len(text)) if char_start >= 0 else None,
        source_hash=page.source_hash if page else None,
        quote_sha256=quote_digest(text),
        geometry_available=bool(node.bbox),
    )


def _page_citation(record: DossierRecord, page_number: int | None) -> Citation | None:
    if page_number is None:
        return None
    page = next((item for item in record.pages if item.page_number == page_number), None)
    if page is None:
        return None
    text = (page.text or "")[:240]
    return Citation(
        node_id=f"page:{page.page_revision_id}",
        page_revision_id=page.page_revision_id,
        text_span=text,
        source_file_id=page.source_file_id,
        page=page.page_number,
        page_range=[page.page_number],
        source_hash=page.source_hash,
        quote_sha256=quote_digest(text),
    )


def _finding(
    digest: str,
    kind: str,
    subject_key: str | None,
    source_node_ids: list[str],
    reason: str,
    review_state: ReviewState,
    relation_type: RelationType | None,
    citations: list[Citation],
    *,
    metadata: dict | None = None,
) -> ContextFinding:
    seed = f"{digest}|{kind}|{subject_key}|{','.join(source_node_ids)}|{reason}"
    return ContextFinding(
        finding_id="context-finding:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24],
        kind=kind,  # type: ignore[arg-type]
        relation_type=relation_type,
        subject_key=subject_key,
        source_node_ids=list(dict.fromkeys(source_node_ids)),
        reason=reason,
        review_state=review_state,
        citations=citations,
        metadata=metadata or {},
    )


def _number_sort(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except ValueError:
        return (10**9, value)
