"""Section 11: cross-page table continuity -- hard guards -> deterministic score ->
merge/split/needs_review, with no LLM gray-zone agent in this build (a genuinely
ambiguous pair must land on NEEDS_REVIEW, never a guess)."""

from contract_ocr.application.use_cases.table_continuity import link_continuities
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Cell, Row, Table


def _table(table_id: str, header: list[str], y1: float, y2: float, n_data_rows: int = 1) -> Table:
    cols = len(header)
    rows = [Row(cells=[Cell(text=f"v{r}{c}") for c in range(cols)]) for r in range(n_data_rows)]
    return Table(
        table_id=table_id,
        bbox=BBox(x1=0.1, y1=y1, x2=0.9, y2=y2),
        geometry_provenance="MEASURED",
        header=header,
        rows=rows,
    )


def test_matching_columns_at_page_edges_with_repeated_header_merges():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)  # bottom of page 1
    nxt = _table("t2", header, y1=0.05, y2=0.4)  # top of page 2
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert len(links) == 1
    link = links[0]
    assert link.decision == "MERGE"
    assert link.from_table_id == "t1" and link.to_table_id == "t2"
    assert "REPEATED_TABLE_HEADER" in link.reason_codes


def test_matching_columns_at_edges_without_repeated_header_is_needs_review():
    prev = _table("t1", ["STT", "Ten hang", "So luong"], y1=0.5, y2=0.9)
    nxt = _table("t2", ["", "", ""], y1=0.05, y2=0.4)  # continuation page: no header row
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "NEEDS_REVIEW"
    assert "INSUFFICIENT_EVIDENCE" in links[0].reason_codes


def test_incompatible_column_count_splits():
    prev = _table("t1", ["STT", "Ten hang", "So luong"], y1=0.5, y2=0.9)
    nxt = _table("t2", ["Ma so", "Gia tri"], y1=0.05, y2=0.4)
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert links[0].confidence == 1.0
    assert "INCOMPATIBLE_COLUMN_SCHEMA" in links[0].reason_codes


def test_tables_not_near_page_edges_split_even_with_matching_columns():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.3, y2=0.5)  # mid-page, not near bottom
    nxt = _table("t2", header, y1=0.4, y2=0.6)  # mid-page, not near top
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert "NOT_AT_PAGE_EDGES" in links[0].reason_codes


def test_non_adjacent_pages_produce_no_link():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4)
    # A table-less page 2 sits between them -- page 3's table must not be compared
    # against page 1's as if they were adjacent.
    links = link_continuities([(1, [prev]), (2, []), (3, [nxt])])
    assert links == []


def test_two_tables_on_the_same_page_do_not_self_link():
    header = ["STT", "Ten hang", "So luong"]
    t1 = _table("t1", header, y1=0.1, y2=0.3)
    t2 = _table("t2", header, y1=0.5, y2=0.9)
    links = link_continuities([(1, [t1, t2])])
    assert links == []


def test_missing_geometry_is_needs_review_not_a_guess():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4)
    nxt = nxt.model_copy(update={"bbox": None, "geometry_provenance": None})
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "NEEDS_REVIEW"
    assert "MISSING_GEOMETRY" in links[0].reason_codes
    assert links[0].confidence == 0.0
