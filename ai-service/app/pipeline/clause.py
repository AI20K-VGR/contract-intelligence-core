from __future__ import annotations

from uuid import uuid4

from app.contracts.models import Chunk, ReviewState, StructuralNode, ValidatedHandoff


class ClauseChunker:
    def chunk(self, handoff: ValidatedHandoff) -> list[Chunk]:
        by_id = {n.node_id: n for n in handoff.nodes}
        chunks: list[Chunk] = []
        for node in handoff.nodes:
            if node.type not in {"CLAUSE", "SECTION", "UNNUMBERED_BLOCK"}:
                continue
            if node.status != "CONFIRMED":
                chunks.append(
                    Chunk(
                        chunk_id=f"chk_{uuid4().hex[:8]}",
                        parent_node_id=node.node_id,
                        page_range=node.page_range,
                        text_span=node.text or node.raw_label,
                        breadcrumb=_breadcrumb(node, by_id),
                        review_state=ReviewState.NEEDS_REVIEW,
                    )
                )
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"chk_{uuid4().hex[:8]}",
                    parent_node_id=node.node_id,
                    page_range=node.page_range,
                    text_span=node.text or node.raw_label,
                    bbox_fragments=[node.bbox] if node.bbox else [],
                    breadcrumb=_breadcrumb(node, by_id),
                    continuation=False,
                    review_state=ReviewState.PASS,
                )
            )
        return chunks


def _breadcrumb(node: StructuralNode, by_id: dict[str, StructuralNode]) -> list[str]:
    labels = [node.raw_label]
    cur = node.parent_id
    while cur and cur in by_id:
        parent = by_id[cur]
        labels.append(parent.raw_label)
        cur = parent.parent_id
    return list(reversed(labels))
