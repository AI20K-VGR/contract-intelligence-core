"""Build outline tree and locate a node on OCR page text."""

from __future__ import annotations

from app.contracts.models import Citation, PageSnapshot, StructuralNode
from app.pipeline.citations import CitationResolver, quote_digest


def build_tree(nodes: list[StructuralNode]) -> list[dict]:
    by_id = {n.node_id: _node_payload(n) for n in nodes}
    for item in by_id.values():
        item["children"] = []
    roots: list[dict] = []
    for n in sorted(nodes, key=lambda x: (x.order, x.node_id)):
        item = by_id[n.node_id]
        parent = n.parent_id
        if parent and parent in by_id:
            by_id[parent]["children"].append(item)
            by_id[parent]["has_children"] = True
        else:
            roots.append(item)
    return roots


def locate(nodes: list[StructuralNode], pages: list[PageSnapshot], node_id: str) -> dict | None:
    node = next((n for n in nodes if n.node_id == node_id), None)
    if node is None:
        return None
    crumb = _breadcrumb(nodes, node)
    unique = (node.structured_value or "").strip()
    needles = [s for s in (unique, node.text, node.raw_label) if s]
    page = next((p for p in pages if node.page_revision_id and p.page_revision_id == node.page_revision_id), None)
    if page is None:
        page = next(
            (
                p
                for p in pages
                if node.source_file_id
                and p.source_file_id == node.source_file_id
                and p.page_in_file == (node.page_in_file or 1)
            ),
            None,
        )
    if page is None:
        preferred = node.page_range[0] if node.page_range else 1
        if not node.source_file_id:
            page = next((p for p in pages if p.page_number == preferred), None)
    hit = _search_page(page, needles)
    span = unique or (hit["span"] if hit else (node.text or node.raw_label)[:220])
    return {
        "node_id": node.node_id,
        "type": node.type,
        "raw_label": node.raw_label,
        "status": node.status,
        "breadcrumb": crumb,
        "page": page.page_number if page else (node.page_range[0] if node.page_range else 1),
        "page_revision_id": (page.page_revision_id if page else node.page_revision_id) or "",
        "bbox": node.bbox,
        "text_span": span,
        "char_start": hit["start"] if hit else None,
        "char_end": hit["end"] if hit else None,
        "in_page_text": bool(hit),
        "quality": page.quality if page else None,
        "file_id": node.source_file_id or (page.source_file_id if page else None),
        "page_in_file": node.page_in_file or (page.page_in_file if page else 1),
        "page_range": node.page_range,
        "source_line_ids": node.source_line_ids,
        "structure_path": " › ".join(crumb),
        "geometry_available": bool(node.bbox),
    }


def citation_for_node(
    nodes: list[StructuralNode],
    pages: list[PageSnapshot],
    node_id: str,
    *,
    text_span: str | None = None,
) -> dict | None:
    """Resolve a citation from the canonical active tree.

    The resolver is intentionally node-first: a citation cannot point to a
    guessed page or a raw label that is not present in the active evidence.
    """

    location = locate(nodes, pages, node_id)
    if location is None:
        return None
    node = next((item for item in nodes if item.node_id == node_id), None)
    # A default node citation must preserve the whole evidence line.  The
    # locator may use a structured value to find a precise character offset,
    # but reducing the citation to that value would hide amendment/context
    # cues such as "sửa ... thành ..." from comparison and review layers.
    requested_span = text_span or ((node.text if node else "") or location.get("text_span") or "")[:240]
    page = next((item for item in pages if item.page_revision_id == location.get("page_revision_id")), None)
    # A reconstructed node can span several pages.  A citation must still be
    # scoped to the page containing the requested subspan; otherwise the node
    # carries line IDs from other page revisions and becomes INVALID even
    # though the quoted role/clause is present in the source.
    if node is not None and requested_span:
        candidate_pages = [
            item for item in pages
            if not node.page_range or item.page_number in set(node.page_range)
        ]
        exact_page = next((item for item in candidate_pages if requested_span in item.text), None)
        if exact_page is not None:
            page = exact_page
            location = dict(location)
            location.update(
                {
                    "page": page.page_number,
                    "page_revision_id": page.page_revision_id,
                    "page_range": [page.page_number],
                    "source_line_ids": [
                        line_id for line_id in (node.source_line_ids or [])
                        if line_id in page.line_texts
                    ],
                    "char_start": None,
                    "char_end": None,
                }
            )
    located_start = location.get("char_start")
    located_end = location.get("char_end")
    span = requested_span
    char_start = -1
    source_range = _span_for_line_ids(page, node.source_line_ids) if page and node and node.source_line_ids else None
    exact_start = (page.text.find(requested_span, *source_range) if source_range else page.text.find(requested_span)) if page and requested_span else -1
    if exact_start >= 0:
        span = requested_span
        char_start = exact_start
    elif page and isinstance(located_start, int) and isinstance(located_end, int):
        # The source page is authoritative. Structured values may differ in
        # case or OCR normalization from the page text.
        if not page.line_texts:
            # Legacy catalog pages do not carry line segmentation. Keep the
            # full source page as the exact evidence span so contextual cues
            # (for example an annex reference plus its amendment wording) are
            # not lost when a node label is only a partial OCR match.
            # Keep the smallest exact source match found by locate() instead
            # of attaching the entire page to a narrow structural node.
            span = location.get("text_span") or page.text
            char_start = page.text.find(span) if span else 0
        else:
            span = page.text[located_start:located_end]
            char_start = located_start
    elif page and node and node.source_line_ids:
        line_span = _span_for_line_ids(page, node.source_line_ids)
        if line_span is not None:
            char_start, char_end = line_span
            span = page.text[char_start:char_end]
    else:
        span = requested_span
        char_start = page.text.find(span) if page and span else -1
    citation = Citation(
        node_id=node_id,
        page_revision_id=location.get("page_revision_id") or "",
        bbox=location.get("bbox") or [],
        text_span=span,
        source_file_id=location.get("file_id"),
        page=location.get("page"),
        page_range=location.get("page_range") or [],
        line_ids=location.get("source_line_ids") or [],
        char_start=location.get("char_start"),
        char_end=location.get("char_end"),
        breadcrumb=location.get("breadcrumb") or [],
        structure_path=location.get("structure_path"),
        geometry_available=bool(location.get("geometry_available")),
    )
    if page is not None:
        citation.char_start = char_start if char_start >= 0 else citation.char_start
        citation.char_end = (
            citation.char_start + len(span)
            if citation.char_start is not None
            else citation.char_end
        )
        citation.source_hash = page.source_hash
        citation.quote_sha256 = quote_digest(span)
        citation.validation_status = CitationResolver([page]).verify(citation).status
    return citation.model_dump()


def _span_for_line_ids(page: PageSnapshot, line_ids: list[str]) -> tuple[int, int] | None:
    ranges: dict[str, tuple[int, int]] = {}
    cursor = 0
    for index, (line_id, line_text) in enumerate(page.line_texts.items()):
        ranges[line_id] = (cursor, cursor + len(line_text))
        cursor += len(line_text) + (1 if index < len(page.line_texts) - 1 else 0)
    selected = [ranges[line_id] for line_id in line_ids if line_id in ranges]
    if not selected:
        return None
    return min(start for start, _ in selected), max(end for _, end in selected)


def _node_payload(n: StructuralNode) -> dict:
    page = n.page_range[0] if n.page_range else None
    return {
        "node_id": n.node_id,
        "type": n.type,
        "raw_label": n.raw_label,
        "status": n.status,
        "page": page,
        "page_range": n.page_range,
        "page_revision_id": n.page_revision_id,
        "bbox": n.bbox,
        "has_children": n.has_children,
        "structured_key": n.structured_key,
        "source_file_id": n.source_file_id,
        "page_in_file": n.page_in_file,
        "structure_level": n.structure_level,
        "scope_id": n.scope_id,
        "heading_confidence": n.heading_confidence,
        "parent_confidence": n.parent_confidence,
        "source_line_ids": n.source_line_ids,
        "is_synthetic": n.is_synthetic,
        "preview": (n.text or n.structured_value or "")[:80],
    }


def _breadcrumb(nodes: list[StructuralNode], node: StructuralNode) -> list[str]:
    by_id = {n.node_id: n for n in nodes}
    labels: list[str] = []
    cur: StructuralNode | None = node
    seen: set[str] = set()
    while cur is not None and cur.node_id not in seen:
        seen.add(cur.node_id)
        labels.append(cur.raw_label)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return list(reversed(labels))


def _search_page(page: PageSnapshot | None, needles: list[str]) -> dict | None:
    if page is None or not page.text:
        return None
    text = page.text
    lower = text.lower()
    for needle in needles:
        n = needle.strip()
        if len(n) < 3:
            continue
        idx = text.find(n)
        if idx < 0:
            idx = lower.find(n.lower())
        if idx < 0 and len(n) > 24:
            idx = lower.find(n[:24].lower())
            n = text[idx : idx + min(len(n), 80)] if idx >= 0 else n
        if idx >= 0:
            end = idx + max(len(n[:180]), 3)
            return {"page": page.page_number, "start": idx, "end": min(end, len(text)), "span": text[idx:end]}
    return None
