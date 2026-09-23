from contract_ocr.reconstruction.header_footer_detector import detect_header_footer
from contract_ocr.reconstruction.table_merger import (
    build_table,
    extract_raw_tables,
    parse_cells,
    tables_continue,
)

from .factories import make_block, make_page


def test_parse_cells_strips_and_drops_surrounding_pipes():
    assert parse_cells("| STT | Hạng mục | Giá |") == ["STT", "Hạng mục", "Giá"]
    assert parse_cells("|     |          | 200 |") == ["", "", "200"]


def _table_row(block_id: str, text: str, y: float) -> object:
    return make_block(block_id, text, type="table_row", bbox=(100, y, 1000, y + 40))


def test_extract_raw_tables_groups_consecutive_table_rows():
    blocks = [
        make_block("p20_h", "ĐIỀU 8. BẢNG GIÁ", type="heading", bbox=(100, 100, 1000, 150)),
        _table_row("p20_r0", "| STT | Hạng mục | Giá |", 200),
        _table_row("p20_r1", "| 1   | A        | 100 |", 240),
        _table_row("p20_r2", "| 2   | B        |     |", 280),
    ]
    page = make_page("doc1", 20, blocks)
    profile = detect_header_footer([page])

    tables = extract_raw_tables(page, profile)
    assert len(tables) == 1
    assert [row.cells for row in tables[0].rows] == [
        ["STT", "Hạng mục", "Giá"],
        ["1", "A", "100"],
        ["2", "B", ""],
    ]


def test_tables_continue_true_on_matching_header_and_columns():
    page20 = make_page(
        "doc1",
        20,
        [
            _table_row("p20_r0", "| STT | Hạng mục | Giá |", 200),
            _table_row("p20_r1", "| 1   | A        | 100 |", 240),
            _table_row("p20_r2", "| 2   | B        |     |", 280),
        ],
    )
    page21 = make_page(
        "doc1",
        21,
        [
            _table_row("p21_r0", "| STT | Hạng mục | Giá |", 100),
            _table_row("p21_r1", "|     |          | 200 |", 140),
            _table_row("p21_r2", "| 3   | C        | 300 |", 180),
        ],
    )
    profile = detect_header_footer([page20, page21])
    previous = extract_raw_tables(page20, profile)[0]
    next_table = extract_raw_tables(page21, profile)[0]

    is_continuation, confidence = tables_continue(previous, next_table)
    assert is_continuation
    assert confidence >= 0.9


def test_tables_continue_false_on_mismatched_column_count():
    page1 = make_page("doc1", 1, [_table_row("a", "| A | B |", 100)])
    page2 = make_page("doc1", 2, [_table_row("b", "| A | B | C |", 100)])
    profile = detect_header_footer([page1, page2])
    is_continuation, confidence = tables_continue(
        extract_raw_tables(page1, profile)[0], extract_raw_tables(page2, profile)[0]
    )
    assert not is_continuation
    assert confidence == 0.0


def test_build_table_single_fragment_standalone():
    page = make_page(
        "doc1",
        5,
        [
            _table_row("r0", "| STT | Tên | Số lượng |", 100),
            _table_row("r1", "| 1 | Bút | 10 |", 140),
            _table_row("r2", "| 2 | Vở | 20 |", 180),
        ],
    )
    profile = detect_header_footer([page])
    fragment = extract_raw_tables(page, profile)[0]
    table = build_table("table_01", [fragment])

    assert table.columns == ["STT", "Tên", "Số lượng"]
    assert table.page_start == table.page_end == 5
    assert [row.values for row in table.rows] == [["1", "Bút", "10"], ["2", "Vở", "20"]]
    assert table.repeated_header_blocks == []


def test_build_table_merges_split_row_and_drops_repeated_header():
    page20 = make_page(
        "doc1",
        20,
        [
            _table_row("p20_r0", "| STT | Hạng mục | Giá |", 200),
            _table_row("p20_r1", "| 1   | A        | 100 |", 240),
            _table_row("p20_r2", "| 2   | B        |     |", 280),
        ],
    )
    page21 = make_page(
        "doc1",
        21,
        [
            _table_row("p21_r0", "| STT | Hạng mục | Giá |", 100),
            _table_row("p21_r1", "|     |          | 200 |", 140),
            _table_row("p21_r2", "| 3   | C        | 300 |", 180),
        ],
    )
    profile = detect_header_footer([page20, page21])
    fragment_20 = extract_raw_tables(page20, profile)[0]
    fragment_21 = extract_raw_tables(page21, profile)[0]

    table = build_table("table_07", [fragment_20, fragment_21])

    assert table.columns == ["STT", "Hạng mục", "Giá"]
    assert table.page_start == 20
    assert table.page_end == 21

    values = [row.values for row in table.rows]
    assert values == [["1", "A", "100"], ["2", "B", "200"], ["3", "C", "300"]]

    row_2 = table.rows[1]
    assert row_2.source_pages == [20, 21]
    assert {ref.block_id for ref in row_2.source_blocks} == {"p20_r2", "p21_r1"}

    # The repeated header on page 21 must not appear as a logical row, but
    # its provenance must be kept.
    assert len(table.repeated_header_blocks) == 1
    assert table.repeated_header_blocks[0].block_id == "p21_r0"
    assert table.repeated_header_blocks[0].page == 21
