"""Table reconstruction for scanned/OCR'd pages (section 9/17).

Uses `infrastructure.image.table_grid.detect_bordered_tables` to find ruling-line
grids directly from pixels (see that module's docstring for why: neither scanned-page
word source wired into this codebase currently produces word-level bbox, so
`table_reconstruct`'s word-alignment approach cannot work here yet). Cell TEXT is then
assigned from lines the page's own OCR pass already recognized -- by bbox-center
containment -- rather than issuing new per-cell OCR calls: reuses work already done
instead of a costly crop-and-re-OCR pass per cell (see docs/ai1-decisions.md for the
tradeoff this was chosen over).

Bordered tables only. Borderless scanned tables are a real, disclosed gap (section 9's
"word bbox alignment" approach needs word-level OCR this codebase does not produce for
scanned pages yet).
"""

from __future__ import annotations

import numpy as np

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Cell, Line, Row, Table
from contract_ocr.domain.enums import GeometryProvenance
from contract_ocr.infrastructure.image.preprocessing import restore_pixel_bbox
from contract_ocr.infrastructure.image.table_grid import detect_bordered_tables

# A grid larger than this is skipped rather than reconstructed: assigning OCR lines to
# hundreds of cells has not been validated at that scale, and a wrong guess on a huge
# table is worse than an honest gap. Every real hit found sweeping this project's own
# 30-sample dataset (n=435 pages) topped out at 13x8=104 cells, well under this cap --
# see docs/ai1-decisions.md for the exact sweep. Not yet threaded through as an explicit
# STRUCTURE_UNAVAILABLE page-level signal (deferred to the validation/recovery phase);
# a skipped grid is silently absent from `tables[]` today, a known, disclosed gap.
MAX_CELLS_PER_TABLE = 300


def build_scanned_tables(
    image: np.ndarray,
    lines: list[Line],
    *,
    document_id: str,
    page_number: int,
    inverse_transform: np.ndarray,
    original_shape: tuple,
) -> list[Table]:
    grids = detect_bordered_tables(image)
    tables: list[Table] = []
    for index, grid in enumerate(grids, 1):
        cell_grid = grid.cells()
        if sum(len(row) for row in cell_grid) > MAX_CELLS_PER_TABLE:
            continue
        built_rows = [
            [_build_cell(cell_px, lines, inverse_transform, original_shape) for cell_px in row]
            for row in cell_grid
        ]
        if not built_rows:
            continue
        header = [cell.text for cell in built_rows[0]]
        table_bbox = restore_pixel_bbox(grid.bbox, inverse_transform, original_shape)
        tables.append(
            Table(
                table_id=f"{document_id}-p{page_number:03d}-t{index:03d}",
                bbox=table_bbox,
                # A direct ruling-line detector output (section 6): MEASURED, not
                # derived from anything else.
                geometry_provenance=GeometryProvenance.MEASURED,
                header=header,
                rows=[Row(cells=row) for row in built_rows[1:]],
            )
        )
    return tables


def _build_cell(
    cell_px: tuple[int, int, int, int],
    lines: list[Line],
    inverse_transform: np.ndarray,
    original_shape: tuple,
) -> Cell:
    bbox = restore_pixel_bbox(cell_px, inverse_transform, original_shape)
    matched = [
        line.text for line in lines if line.bbox is not None and _center_within(line.bbox, bbox)
    ]
    return Cell(
        text=" ".join(matched),
        bbox=bbox,
        geometry_provenance=GeometryProvenance.MEASURED,
    )


def _center_within(line_bbox: BBox, cell_bbox: BBox) -> bool:
    cx, cy = (line_bbox.x1 + line_bbox.x2) / 2, (line_bbox.y1 + line_bbox.y2) / 2
    return cell_bbox.x1 <= cx <= cell_bbox.x2 and cell_bbox.y1 <= cy <= cell_bbox.y2
