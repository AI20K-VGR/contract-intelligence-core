"""Build the clause hierarchy from OCR text, then map optional geometry.

OCR text is the source of truth for clause content.  Bounding boxes are only
the source of truth for position: lines without geometry still participate in
boundary detection and remain in ``StructuralNode.text``.  After the text tree
is complete, a separate geometry pass selects only the first/last positioned
line on each page as anchors.  It never crops a clause bbox or re-OCRs that crop.

This reuses `contract_ocr.reconstruction`'s marker parser
(`clause_parser.parse_marker`) and tree builder (`hierarchy_builder.
build_hierarchy`) directly — both are pure, already-tested functions with no
dependency on the rest of that package's `Block`-based boundary-resolution
machinery. Every line of every successfully-processed page becomes one
`LogicalSegment` in document reading order; `build_hierarchy` places each
segment under whichever clause marker is currently open.

The hierarchy builder keeps its active clause across page boundaries, so body
text on the next page remains in that clause until a new marker opens. This is
deterministic reading-order continuation; it does not use bbox proximity.
Running headers/footers/page numbers (`running_text.detect_running_lines`) are
left out of the segment stream first -- otherwise a clause open at a page break
would absorb the footer of its page and the header of the next one, and its
page range would stretch onto a page its own text never reaches. A page that
repeats an earlier page verbatim (`Page.duplicate_of`) is left out too: its
clauses are already in the stream once.
"""

from __future__ import annotations

from contract_ocr.application.use_cases.running_text import detect_running_lines
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Document as InternalDocument
from contract_ocr.domain.entities import Line as InternalLine
from contract_ocr.domain.enums import Status
from contract_ocr.domain.snapshot import NormalizedBBox, StructuralNode, StructuralRegion
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
        pages_by_line_id: dict[str, int] = {}
        running = detect_running_lines(document)
        for page in document.pages:
            if page.status is not Status.SUCCESS or page.duplicate_of is not None:
                continue
            for line in page.lines:
                if not line.text.strip() or (page.page_number, line.line_id) in running:
                    continue
                lines_by_id[line.line_id] = line
                pages_by_line_id[line.line_id] = page.page_number
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
        return [
            self._to_node(clause, lines_by_id, pages_by_line_id, line_id_map)
            for clause in flat_clauses
        ]

    def _to_node(
        self,
        clause: Clause,
        lines_by_id: dict[str, InternalLine],
        pages_by_line_id: dict[str, int],
        line_id_map: dict[str, str] | None,
    ) -> StructuralNode:
        internal_line_ids = [ref.block_id for ref in clause.source_blocks if ref.block_id]
        if line_id_map is None:
            external_line_ids = list(internal_line_ids)
        else:
            external_line_ids = [
                line_id_map[lid] for lid in internal_line_ids if lid in line_id_map
            ]
        regions = self._map_geometry(internal_line_ids, lines_by_id, pages_by_line_id)
        bbox_normalized, provenance = self._legacy_bbox(regions)
        node_type = _node_type(clause)
        # Preserve the OCR stream verbatim at line granularity. The hierarchy
        # builder joins parts with spaces for its generic reconstruction model,
        # but clause payloads should not erase source line boundaries.
        clause_text = "\n".join(lines_by_id[line_id].text for line_id in internal_line_ids)
        return StructuralNode(
            node_id=clause.clause_id,
            type=node_type,
            label_raw=clause.marker,
            label_normalized=f"{node_type}_{clause.clause_id}",
            parent_id=clause.parent_id,
            page_start=clause.page_start,
            page_end=clause.page_end,
            text=clause_text,
            line_ids=external_line_ids,
            regions=regions,
            bbox_normalized=bbox_normalized,
            geometry_provenance=provenance,
        )

    @staticmethod
    def _map_geometry(
        line_ids: list[str],
        lines_by_id: dict[str, InternalLine],
        pages_by_line_id: dict[str, int],
    ) -> list[StructuralRegion]:
        """Map clause boundaries to geometry using sparse start/end anchors."""
        positioned = [
            lines_by_id[line_id]
            for line_id in line_ids
            if line_id in lines_by_id and lines_by_id[line_id].bbox is not None
        ]
        by_page: dict[int, list[InternalLine]] = {}
        for line in positioned:
            page_number = pages_by_line_id[line.line_id]
            by_page.setdefault(page_number, []).append(line)

        regions: list[StructuralRegion] = []
        for page_number, page_lines in by_page.items():
            start_box, start_provenance = BuildStructure._anchor_geometry(page_lines[0], False)
            end_box, end_provenance = BuildStructure._anchor_geometry(page_lines[-1], True)
            anchors = [("START", start_box, start_provenance)]
            if end_box != start_box:
                anchors.append(("END", end_box, end_provenance))
            for anchor, box, provenance in anchors:
                regions.append(
                    StructuralRegion(
                        page_number=page_number,
                        bbox_normalized=[box.x1, box.y1, box.x2, box.y2],
                        geometry_provenance=provenance,
                        anchor=anchor,
                    )
                )
        return regions

    @staticmethod
    def _anchor_geometry(line: InternalLine, use_last: bool) -> tuple[BBox, str]:
        """Prefer one boundary word; fall back to the containing OCR line/block."""
        positioned_words = [word for word in line.words if word.bbox is not None]
        if positioned_words:
            word = positioned_words[-1] if use_last else positioned_words[0]
            return word.bbox, word.geometry_provenance
        return line.bbox, line.geometry_provenance

    @staticmethod
    def _legacy_bbox(
        regions: list[StructuralRegion],
    ) -> tuple[NormalizedBBox | None, str | None]:
        """Keep the v1 single bbox for old consumers; new code uses regions."""
        if not regions:
            return None, None
        # A single normalized bbox cannot truthfully represent coordinates on
        # multiple pages.  Multi-page nodes expose only their page-scoped
        # regions; legacy consumers receive no fabricated document-wide box.
        if len({region.page_number for region in regions}) != 1:
            return None, None
        boxes = [region.bbox_normalized for region in regions]
        box = BBox(
            x1=min(b[0] for b in boxes),
            y1=min(b[1] for b in boxes),
            x2=max(b[2] for b in boxes),
            y2=max(b[3] for b in boxes),
        )
        return [box.x1, box.y1, box.x2, box.y2], "DERIVED"
