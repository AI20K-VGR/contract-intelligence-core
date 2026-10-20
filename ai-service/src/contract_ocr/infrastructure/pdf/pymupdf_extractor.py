from collections import defaultdict

import pymupdf

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Cell, Line, Page, Row, Table, Word
from contract_ocr.domain.enums import GeometryProvenance


class PyMuPDFExtractor:
    def open(self, path: str) -> pymupdf.Document:
        return pymupdf.open(path)

    def evidence(self, page: pymupdf.Page) -> tuple[int, int, int, float, str]:
        words = page.get_text("words")
        spans = sum(
            len(line["spans"])
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
        )
        # Exact rectangle union via vertical slabs; repeated/overlapping images count once.
        rects = [
            pymupdf.Rect(info["bbox"]) * page.rotation_matrix & page.rect
            for info in page.get_image_info()
        ]
        xs = sorted({x for r in rects for x in (r.x0, r.x1)})
        area = 0.0
        for left, right in zip(xs, xs[1:]):
            intervals = sorted(
                (r.y0, r.y1) for r in rects if r.x0 < right and r.x1 > left and not r.is_empty
            )
            end, height = -float("inf"), 0.0
            for low, high in intervals:
                height += max(0.0, high - max(low, end))
                end = max(end, high)
            area += (right - left) * height
        text = page.get_text()
        return (
            len(text.strip()),
            len(words),
            spans,
            min(1.0, area / page.rect.get_area()),
            text,
        )

    def extract(self, page: pymupdf.Page, document_id: str) -> Page:
        width, height = page.rect.width, page.rect.height
        groups = defaultdict(list)
        for index, word in enumerate(page.get_text("words", sort=True), 1):
            rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
            box = BBox.normalize(list(rect), width, height)
            groups[(word[5], word[6])].append(
                Word(
                    word_id=f"{document_id}-p{page.number + 1:03d}-w{index:04d}",
                    text=word[4],
                    bbox=box,
                    # Each word's own rect comes directly from the PDF's glyph
                    # layout — a deterministic measurement, not a guess.
                    geometry_provenance=GeometryProvenance.MEASURED,
                )
            )
        lines = []
        for index, words in enumerate(groups.values(), 1):
            boxes = [w.bbox for w in words]
            box = BBox(
                x1=min(b.x1 for b in boxes),
                y1=min(b.y1 for b in boxes),
                x2=max(b.x2 for b in boxes),
                y2=max(b.y2 for b in boxes),
            )
            lines.append(
                Line(
                    line_id=f"{document_id}-p{page.number + 1:03d}-l{index:04d}",
                    text=" ".join(w.text for w in words),
                    words=words,
                    bbox=box,
                    # Not independently measured: this is the union of the words'
                    # own measured boxes above, so it is DERIVED (section 6).
                    geometry_provenance=GeometryProvenance.DERIVED,
                )
            )
        return Page(
            page_number=page.number + 1,
            width=width,
            height=height,
            dimension_unit="pt",
            rotation=page.rotation,
            engine="pymupdf",
            model=pymupdf.VersionBind,
            lines=lines,
            tables=self._extract_tables(page, width, height, document_id),
            geometry_available=bool(lines),
        )

    def _extract_tables(
        self, page: pymupdf.Page, width: float, height: float, document_id: str
    ) -> list[Table]:
        """Native table detection: PyMuPDF's own `find_tables()` (ruling-line and
        text-alignment based) on a text-layer page. This is a direct, deterministic
        detector output -- MEASURED, not something this codebase derived. Scanned
        pages have no native structure to detect this way and are not covered here
        (see docs/ai1-current-state.md: no fragment/table-region detector exists
        yet for OCR-only pages; this is a disclosed, deferred gap, not a silent
        one -- BuildSnapshot marks those pages' table_status as NOT_CHECKED rather
        than implying an empty result means "no table")."""
        tables: list[Table] = []
        try:
            finder = page.find_tables()
        except Exception:
            # A malformed/unsupported page structure must not fail the whole
            # page's extraction over table detection alone.
            return tables
        for index, table in enumerate(finder.tables, 1):
            extracted = table.extract()
            if not extracted:
                continue
            header_texts = [str(v) if v is not None else "" for v in extracted[0]]
            rows: list[Row] = []
            for row, row_texts in zip(table.rows[1:], extracted[1:], strict=False):
                cells = []
                for cell_bbox, text in zip(row.cells, row_texts, strict=False):
                    if cell_bbox is None:
                        cells.append(Cell(text=text or ""))
                        continue
                    rect = pymupdf.Rect(cell_bbox) * page.rotation_matrix
                    cells.append(
                        Cell(
                            text=text or "",
                            bbox=BBox.normalize(list(rect), width, height),
                            geometry_provenance=GeometryProvenance.MEASURED,
                        )
                    )
                rows.append(Row(cells=cells))
            table_rect = pymupdf.Rect(table.bbox) * page.rotation_matrix
            tables.append(
                Table(
                    table_id=f"{document_id}-p{page.number + 1:03d}-t{index:03d}",
                    bbox=BBox.normalize(list(table_rect), width, height),
                    geometry_provenance=GeometryProvenance.MEASURED,
                    header=header_texts,
                    rows=rows,
                )
            )
        return tables
