from contract_ocr.reconstruction.hierarchy_builder import LogicalSegment, build_hierarchy
from contract_ocr.reconstruction.models import SourceBlockRef


def _segment(text: str, page: int = 1) -> LogicalSegment:
    return LogicalSegment(
        text=text,
        page_start=page,
        page_end=page,
        source_blocks=[SourceBlockRef(page=page, block_id=f"b_{text[:6]}")],
    )


def _find(clauses, clause_id: str):
    return next(c for c in clauses if c.clause_id == clause_id)


def test_build_hierarchy_case9_numbering_tree():
    segments = [
        _segment("Điều 5. Nghĩa vụ thanh toán"),
        _segment("5.1 Bên mua phải thanh toán đúng hạn."),
        _segment("(a) Thanh toán bằng chuyển khoản."),
        _segment("(i) Trong vòng 30 ngày."),
        _segment("(ii) Có xác nhận của ngân hàng."),
        _segment("(b) Thanh toán bằng tiền mặt."),
        _segment("5.2 Bên bán phải xuất hóa đơn."),
    ]

    sections, clauses = build_hierarchy(segments)

    assert len(sections) == 1
    root = sections[0]
    assert root.clause_id == "5"
    assert root.level == 1
    assert root.parent_id is None
    assert [child.clause_id for child in root.children] == ["5.1", "5.2"]

    clause_5_1 = root.children[0]
    assert clause_5_1.level == 2
    assert [child.clause_id for child in clause_5_1.children] == ["5.1.a", "5.1.b"]

    clause_a = clause_5_1.children[0]
    assert clause_a.level == 3
    assert [child.clause_id for child in clause_a.children] == ["5.1.a.i", "5.1.a.ii"]
    assert clause_a.children[0].level == 4
    assert clause_a.children[1].level == 4

    clause_b = clause_5_1.children[1]
    assert clause_b.level == 3
    assert clause_b.children == []

    clause_5_2 = root.children[1]
    assert clause_5_2.level == 2
    assert clause_5_2.parent_id == "5"

    flat_ids = {c.clause_id for c in clauses}
    assert flat_ids == {"5", "5.1", "5.1.a", "5.1.a.i", "5.1.a.ii", "5.1.b", "5.2"}
    for clause in clauses:
        assert clause.children == []


def test_build_hierarchy_derives_section_title():
    segments = [_segment("Điều 5. Nghĩa vụ thanh toán")]
    sections, _ = build_hierarchy(segments)
    assert sections[0].title == "Nghĩa vụ thanh toán"


def test_build_hierarchy_appends_unmarked_text_to_open_clause():
    segments = [
        _segment("5.1 Bên mua phải thanh toán."),
        _segment("Việc thanh toán được thực hiện bằng VND."),
    ]
    sections, clauses = build_hierarchy(segments)
    clause = _find(clauses, "5.1")
    assert "Bên mua phải thanh toán." in clause.text
    assert "Việc thanh toán được thực hiện bằng VND." in clause.text
    assert len(clause.source_blocks) == 2
