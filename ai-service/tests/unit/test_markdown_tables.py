"""Mistral OCR returns a real table as literal GFM pipe-table markdown, not
pre-parsed cells -- this covers the parser that turns it back into a `Table`."""

from contract_ocr.domain.bbox import BBox
from contract_ocr.infrastructure.ocr.markdown_tables import (
    build_table_from_block,
    clean_markdown_text,
    parse_markdown_pipe_table,
    rectangularize,
)


def test_clean_markdown_text_strips_heading_image_bold_and_latex_escapes():
    assert clean_markdown_text("# DIEU 1. Muc dich") == "DIEU 1. Muc dich"
    assert clean_markdown_text("\\(30\\%\\)") == "30%"
    assert clean_markdown_text("**Tổng cộng**") == "Tổng cộng"
    assert clean_markdown_text("![stamp](img-0.png)") == "[image: stamp]"


def test_parse_markdown_pipe_table_finds_first_table_block():
    text = (
        "Some prose before.\n\n"
        "| STT | Ten hang | So luong |\n"
        "| --- | --- | --- |\n"
        "| 1 | Hang A | 10 |\n"
        "| 2 | Hang B | 20 |\n\n"
        "Some prose after."
    )
    rows = parse_markdown_pipe_table(text)
    assert rows == [
        ["STT", "Ten hang", "So luong"],
        ["1", "Hang A", "10"],
        ["2", "Hang B", "20"],
    ]


def test_parse_markdown_pipe_table_returns_none_without_a_pipe_table():
    assert parse_markdown_pipe_table("Just a paragraph of prose, no table here.") is None


def test_parse_markdown_pipe_table_keeps_escaped_pipe_and_html_line_break():
    text = (
        "| STT | Nội dung | Ghi chú |\n"
        "| --- | --- | --- |\n"
        r"| 1 | Điều kiện A \| B | Dòng một<br>Dòng hai |"
    )

    rows = parse_markdown_pipe_table(text)

    assert rows == [
        ["STT", "Nội dung", "Ghi chú"],
        ["1", "Điều kiện A | B", "Dòng một\nDòng hai"],
    ]


def test_rectangularize_pads_short_rows_without_shifting_columns():
    rows, col_count = rectangularize([["a", "b", "c"], ["d", "e"]])
    assert col_count == 3
    assert rows == [["a", "b", "c"], ["d", "e", None]]


def test_rectangularize_empty_input():
    assert rectangularize([]) == ([], 0)


def test_build_table_from_block_measures_table_bbox_and_claims_cell_bbox():
    content = "| STT | Ten hang |\n| --- | --- |\n| 1 | Hang A |\n| 2 | Hang B |"
    block_bbox = BBox(x1=0.1, y1=0.2, x2=0.9, y2=0.6)
    table = build_table_from_block(
        table_id="t1", block_bbox=block_bbox, block_content=content, heading_before="Phụ lục 01"
    )
    assert table is not None
    assert table.table_id == "t1"
    assert table.bbox == block_bbox
    assert table.geometry_provenance == "MEASURED"
    assert table.header == ["STT", "Ten hang"]
    assert table.heading_before == "Phụ lục 01"
    assert [c.text for row in table.rows for c in row.cells] == ["1", "Hang A", "2", "Hang B"]
    # Cell bboxes are an even split of the block's own real bbox, not a real
    # per-cell detection -- CLAIMED, not MEASURED (see the module's own docstring).
    eps = 1e-9
    for row in table.rows:
        for cell in row.cells:
            assert cell.geometry_provenance == "CLAIMED"
            assert block_bbox.x1 - eps <= cell.bbox.x1 <= cell.bbox.x2 <= block_bbox.x2 + eps
            assert block_bbox.y1 - eps <= cell.bbox.y1 <= cell.bbox.y2 <= block_bbox.y2 + eps


def test_build_table_from_block_returns_none_when_content_has_no_table():
    block_bbox = BBox(x1=0.1, y1=0.2, x2=0.9, y2=0.6)
    table = build_table_from_block(
        table_id="t1", block_bbox=block_bbox, block_content="Just a paragraph, no pipes here."
    )
    assert table is None


def test_build_table_from_block_pads_a_short_row_instead_of_dropping_a_column():
    # A merged cell the model didn't pad itself: row 2 has one fewer cell than the
    # header -- must not shift "Hang B"'s quantity into the wrong column.
    content = (
        "| STT | Ten hang | So luong |\n| --- | --- | --- |\n| 1 | Hang A | 10 |\n| 2 | Hang B |"
    )
    block_bbox = BBox(x1=0.0, y1=0.0, x2=1.0, y2=0.3)
    table = build_table_from_block(table_id="t1", block_bbox=block_bbox, block_content=content)
    assert table is not None
    assert len(table.rows[1].cells) == 3
    assert table.rows[1].cells[2].text == ""
