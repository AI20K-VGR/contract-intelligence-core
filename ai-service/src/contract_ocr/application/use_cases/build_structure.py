"""Builds the document's clause/section hierarchy (`StructuralNode`, section 8)
from real OCR lines.

This reuses `contract_ocr.reconstruction`'s marker parser
(`clause_parser.parse_marker`) and tree builder (`hierarchy_builder.
build_hierarchy`) directly — both are pure, already-tested functions with no
dependency on the rest of that package's `Block`-based boundary-resolution
machinery. Every line of every successfully-processed page becomes one
`LogicalSegment` in document reading order; `build_hierarchy` places each
segment under whichever clause marker is currently open.

Known, disclosed limitation: this does **not** run the reconstruction
pipeline's cross-page boundary resolver (`reconstruction.pipeline.
reconstruct_document`). A clause whose body is genuinely split across a page
break is not spliced back together — it surfaces as two separate segments
under whichever clause was open on each page, rather than one continuous
node. Cross-page structural continuity is the same class of problem as
cross-page table continuity (section 11) and is deferred to that pass. This
still satisfies the section-8 requirement that "every node must be
resolvable to evidence": every node's `line_ids` are real OCR line ids.
"""

from __future__ import annotations

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Document as InternalDocument
from contract_ocr.domain.entities import Line as InternalLine
from contract_ocr.domain.enums import Status
from contract_ocr.domain.snapshot import NormalizedBBox, StructuralNode
from contract_ocr.reconstruction.hierarchy_builder import LogicalSegment, build_hierarchy
from contract_ocr.reconstruction.models import ResolutionMethod, SourceBlockRef
from contract_ocr.reconstruction.schemas.document import Clause

_NODE_TYPE_BY_LEVEL = {1: "ARTICLE", 2: "CLAUSE"}  # level >= 3 collapses to "POINT"


def _node_type(clause: Clause) -> str:
    # `hierarchy_builder` gives body text with no recognized marker at all its
    # own root node (rather than discarding it) but leaves `marker` unset --
    # such a node is not really an "ARTICLE" just because it landed at level 1.
    if clause.marker is None:
        return "UNMARKED"
    return _NODE_TYPE_BY_LEVEL.get(clause.level, "POINT")


class BuildStructure:
    def execute(
        self, document: InternalDocument, line_id_map: dict[str, str] | None = None
    ) -> list[StructuralNode]:
        """`line_id_map` translates the internal `Line.line_id` this module reasons
        about into the externally-visible `SnapshotLine.line_id` a consumer can
        actually resolve (the two id schemes differ -- see build_snapshot.py's
        `id_prefix`/line numbering). Pass `None` only for standalone use against
        internal `Line` ids directly (e.g. unit tests); `BuildSnapshot` always
        passes the real map it built while assembling `pages`. A line absent from
        the map (no bbox, so it never made it into the snapshot) is silently
        excluded from `line_ids` rather than falling back to an unresolvable id --
        a node must never claim evidence that isn't actually in the snapshot.
        """
        segments: list[LogicalSegment] = []
        lines_by_id: dict[str, InternalLine] = {}
        for page in document.pages:
            if page.status is not Status.SUCCESS:
                continue
            for line in page.lines:
                if not line.text.strip():
                    continue
                lines_by_id[line.line_id] = line
                segments.append(
                    LogicalSegment(
                        text=line.text,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        source_blocks=[
                            SourceBlockRef(
                                page=page.page_number,
                                block_id=line.line_id,
                                char_start=0,
                                char_end=len(line.text),
                            )
                        ],
                        was_merged=False,
                        method=ResolutionMethod.RULE,
                        confidence=1.0,
                    )
                )
        _, flat_clauses = build_hierarchy(segments)
        return [self._to_node(clause, lines_by_id, line_id_map) for clause in flat_clauses]

    def _to_node(
        self,
        clause: Clause,
        lines_by_id: dict[str, InternalLine],
        line_id_map: dict[str, str] | None,
    ) -> StructuralNode:
        internal_line_ids = [ref.block_id for ref in clause.source_blocks if ref.block_id]
        if line_id_map is None:
            external_line_ids = list(internal_line_ids)
        else:
            external_line_ids = [
                line_id_map[lid] for lid in internal_line_ids if lid in line_id_map
            ]
        bbox_normalized, provenance = self._union_bbox(internal_line_ids, lines_by_id)
        node_type = _node_type(clause)
        return StructuralNode(
            node_id=clause.clause_id,
            type=node_type,
            label_raw=clause.marker,
            label_normalized=f"{node_type}_{clause.clause_id}",
            parent_id=clause.parent_id,
            page_start=clause.page_start,
            page_end=clause.page_end,
            line_ids=external_line_ids,
            bbox_normalized=bbox_normalized,
            geometry_provenance=provenance,
        )

    @staticmethod
    def _union_bbox(
        line_ids: list[str], lines_by_id: dict[str, InternalLine]
    ) -> tuple[NormalizedBBox | None, str | None]:
        boxes = [
            lines_by_id[line_id].bbox
            for line_id in line_ids
            if line_id in lines_by_id and lines_by_id[line_id].bbox is not None
        ]
        if not boxes:
            return None, None
        box = BBox(
            x1=min(b.x1 for b in boxes),
            y1=min(b.y1 for b in boxes),
            x2=max(b.x2 for b in boxes),
            y2=max(b.y2 for b in boxes),
        )
        # A region bbox unioning other trusted geometry is DERIVED, never
        # MEASURED (section 6) -- even when every constituent line was itself
        # MEASURED, the union itself was not independently measured.
        return [box.x1, box.y1, box.x2, box.y2], "DERIVED"
