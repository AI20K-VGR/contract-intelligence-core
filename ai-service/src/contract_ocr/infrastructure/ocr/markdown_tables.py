"""Turns Mistral OCR's own markdown output into structured tables.

Mistral's dedicated OCR endpoint (`client.ocr.process`, see mistral_ocr.py) returns a
real table as literal GFM pipe-table syntax (`| cell | cell |`) inline in its
markdown, not as pre-parsed cells -- this module is the missing "parse that syntax
back into rows/columns" step, ported from `backend/app/document_processing.py`
(`_parse_markdown_pipe_table` / `_split_table_row` / `_rectangularize` /
`_clean_vision_markdown_text`), which already runs this exact parser against Mistral
markdown in production. Every cell's bbox is an even split of the table BLOCK's own
real (Mistral-measured) bbox by row/column index -- not a real per-cell detection --
so it is marked `GeometryProvenance.CLAIMED`: the honest "don't cite this exact
position" bucket per its own docstring (`domain/enums.py`), even though the literal
definition there ("a coordinate supplied by a model") describes asking a model for
coordinates rather than synthesizing them ourselves -- CLAIMED is still the closer
fit of the three available values, since MEASURED and DERIVED both imply the
position genuinely reflects where the content sits, which an even split does not.
The table's own bbox, by contrast, IS a real Mistral measurement and stays MEASURED.
"""

from __future__ import annotations

import re

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Cell, Row, Table
from contract_ocr.domain.enums import GeometryProvenance

_TABLE_ROW_RE = re.compile(r"^\s*\|(.*)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^[\s|:-]+$")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_MARKDOWN_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HTML_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LATEX_ESCAPE_RE = re.compile(r"\\([%$_&#{}])")


def clean_markdown_text(text: str) -> str:
    """Strips Markdown/LaTeX artifacts Mistral's OCR endpoint's own output style
    introduces (a heading as "# DIEU 1. ...", "\\(30\\%\\)" LaTeX-escaping around a
    plain "30%", `**bold**` on a totals row, an `![...](...)` image reference for a
    stamp/signature) that a plain-text consumer was never built to expect. Never
    drops real content, only the syntax wrapped around it.
    """
    text = _MARKDOWN_HEADING_RE.sub("", text)
    text = _MARKDOWN_IMAGE_RE.sub(lambda m: f"[image: {m.group(1) or m.group(2)}]", text)
    text = _MARKDOWN_BOLD_RE.sub(r"\1", text)
    text = _HTML_BREAK_RE.sub("\n", text)
    text = text.replace("\\(", "").replace("\\)", "")
    text = _LATEX_ESCAPE_RE.sub(r"\1", text)
    return text.strip()


def _split_table_row(line: str) -> list[str]:
    match = _TABLE_ROW_RE.match(line)
    inner = match.group(1) if match else line
    # A literal pipe inside a cell is escaped as ``\|`` in GFM.  Splitting on
    # every pipe created phantom columns and shifted/truncated the remaining text.
    cells = re.split(r"(?<!\\)\|", inner)
    return [clean_markdown_text(cell.replace(r"\|", "|")) for cell in cells]


def parse_markdown_pipe_table(text: str) -> list[list[str]] | None:
    """Finds the first GFM pipe-table (a header row immediately followed by a
    |---|---| separator row) in `text` and returns its header + body rows, header
    included as the first row. Returns None if no such block is found -- a "table"
    block whose content turned out not to actually contain pipe syntax.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (
            _TABLE_ROW_RE.match(line)
            and nxt is not None
            and _TABLE_ROW_RE.match(nxt)
            and _TABLE_SEPARATOR_RE.match(nxt)
            and "-" in nxt
        ):
            rows = [_split_table_row(line)]
            j = i + 2
            while j < len(lines) and _TABLE_ROW_RE.match(lines[j]):
                rows.append(_split_table_row(lines[j]))
                j += 1
            return rows
    return None


def rectangularize(rows: list[list[str | None]]) -> tuple[list[list[str | None]], int]:
    """Pads every row to the widest row's length so the table is a rectangular grid
    -- a row with fewer cells than another (a merged cell) gets trailing blanks
    rather than shifting every later row's columns out of alignment."""
    if not rows:
        return [], 0
    col_count = max(len(row) for row in rows)
    return [row + [None] * (col_count - len(row)) for row in rows], col_count


def build_table_from_block(
    *,
    table_id: str,
    block_bbox: BBox,
    block_content: str,
    heading_before: str | None = None,
) -> Table | None:
    """Parses one Mistral OCR `type == "table"` block's markdown content into a
    `Table`, anchored to that block's own real bbox. Returns None when the block's
    content turns out not to contain a parseable pipe-table, or is degenerate (no
    columns, or a zero-area bbox that an even split cannot divide) -- the caller then
    simply has no table for that block, never a guessed one.
    """
    rows_text = parse_markdown_pipe_table(block_content)
    if not rows_text:
        return None
    rows, col_count = rectangularize(rows_text)
    if col_count == 0 or not rows:
        return None
    x1, y1, x2, y2 = block_bbox.x1, block_bbox.y1, block_bbox.x2, block_bbox.y2
    if x2 <= x1 or y2 <= y1:
        return None
    row_height = (y2 - y1) / len(rows)
    col_width = (x2 - x1) / col_count

    def _cell(text: str | None, row_index: int, col_index: int) -> Cell:
        return Cell(
            text=text or "",
            bbox=BBox(
                x1=x1 + col_index * col_width,
                y1=y1 + row_index * row_height,
                x2=x1 + (col_index + 1) * col_width,
                y2=y1 + (row_index + 1) * row_height,
            ),
            geometry_provenance=GeometryProvenance.CLAIMED,
        )

    header, body = rows[0], rows[1:]
    return Table(
        table_id=table_id,
        bbox=block_bbox,
        geometry_provenance=GeometryProvenance.MEASURED,
        header=[h or "" for h in header],
        rows=[
            Row(cells=[_cell(text, row_index + 1, col_index) for col_index, text in enumerate(row)])
            for row_index, row in enumerate(body)
        ],
        heading_before=heading_before,
    )
