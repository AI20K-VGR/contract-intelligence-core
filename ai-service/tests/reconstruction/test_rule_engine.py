from contract_ocr.reconstruction.boundary_detector import detect_boundary
from contract_ocr.reconstruction.header_footer_detector import detect_header_footer
from contract_ocr.reconstruction.models import (
    Action,
    DocumentState,
    EntityType,
    ReconstructionTarget,
    Relationship,
)
from contract_ocr.reconstruction.rule_engine import resolve_by_rule

from .factories import make_block, make_page


def _context(
    previous_blocks, next_blocks, previous_page_num=10, next_page_num=11, document_state=None
):
    previous_page = make_page("doc1", previous_page_num, previous_blocks)
    next_page = make_page("doc1", next_page_num, next_blocks)
    profile = detect_header_footer([previous_page, next_page])
    return detect_boundary(previous_page, next_page, profile, document_state)


def test_case1_continue_paragraph_across_pages():
    context = _context(
        [make_block("p10_b02", "Bên mua phải thanh toán trong vòng")],
        [make_block("p11_b01", "30 ngày kể từ ngày nhận được hóa đơn hợp lệ.")],
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.CONTINUE_PARAGRAPH
    assert action.action == Action.MERGE_BLOCKS
    assert action.entity_type == EntityType.PARAGRAPH
    assert action.confidence >= 0.85
    assert not action.requires_review
    assert [(b.page, b.block_id) for b in action.source_blocks] == [
        (10, "p10_b02"),
        (11, "p11_b01"),
    ]


def test_case2_new_clause():
    context = _context(
        [make_block("p10_b09", "... thực hiện nghĩa vụ thanh toán.")],
        [make_block("p11_b01", "5.2 Phương thức thanh toán")],
        document_state=DocumentState(active_section="5"),
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.NEW_CLAUSE
    assert action.action == Action.NEW_CLAUSE
    assert action.entity_type == EntityType.CLAUSE
    assert action.confidence >= 0.85
    assert action.target is not None
    assert action.target.node_id == "5.2"
    assert action.target.parent_id == "5"


def test_case2_new_section_for_dieu_marker():
    context = _context(
        [make_block("p10_b09", "... đã hoàn tất theo quy định.")],
        [make_block("p11_b01", "Điều 6. BẢO MẬT THÔNG TIN")],
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.NEW_SECTION
    assert action.action == Action.NEW_SECTION
    assert action.entity_type == EntityType.SECTION
    assert action.target == ReconstructionTarget(node_id="6", parent_id=None)


def test_case3_continue_clause_merges_into_active_clause():
    context = _context(
        [make_block("p10_b05", "5.3 Bên A có trách nhiệm")],
        [make_block("p11_b01", "đảm bảo việc bàn giao đúng tiến độ.")],
        document_state=DocumentState(active_section="5", active_clause="5.3"),
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.CONTINUE_CLAUSE
    assert action.action == Action.MERGE_BLOCKS
    assert action.entity_type == EntityType.CLAUSE
    assert action.confidence >= 0.85
    assert action.target.node_id == "5.3"
    assert action.target.parent_id == "5"


def test_case4_list_continuation_attaches_under_active_clause():
    context = _context(
        [
            make_block("p10_b06", "(a) Điều kiện thứ nhất."),
            make_block("p10_b07", "(b) Điều kiện thứ hai."),
        ],
        [make_block("p11_b01", "(c) Điều kiện thứ ba.")],
        document_state=DocumentState(active_section="5", active_clause="5.1"),
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.LIST_CONTINUE
    assert action.action == Action.CONTINUE_LIST
    assert action.entity_type == EntityType.LIST_ITEM
    assert action.confidence >= 0.85
    assert action.target.node_id == "5.1.c"
    assert action.target.parent_id == "5.1"


def test_case4_roman_list_continuation():
    context = _context(
        [make_block("p10_b06", "(i) Điều kiện đầu tiên.")],
        [make_block("p11_b01", "(ii) Điều kiện tiếp theo.")],
    )
    action = resolve_by_rule(context)
    assert action.relationship == Relationship.LIST_CONTINUE
    assert action.action == Action.CONTINUE_LIST


def test_new_list_item_that_does_not_continue_a_sequence_attaches_as_child():
    # "(a)" appears fresh — nothing open it could be a *sequence successor*
    # of — so it attaches under the active clause instead of NEW_CLAUSE.
    context = _context(
        [make_block("p10_b09", "5.2 Phương thức thanh toán được quy định như sau:")],
        [make_block("p11_b01", "(a) Chuyển khoản ngân hàng.")],
        document_state=DocumentState(active_section="5", active_clause="5.2"),
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.action == Action.ATTACH_CHILD
    assert action.entity_type == EntityType.LIST_ITEM
    assert action.target.node_id == "5.2.a"
    assert action.target.parent_id == "5.2"


def test_case5_incomplete_last_row_resolves_to_row_continue():
    context = _context(
        [
            make_block("p20_r0", "| STT | Hạng mục | Giá |", type="table_row"),
            make_block("p20_r1", "| 1   | A        | 100 |", type="table_row"),
            make_block("p20_r2", "| 2   | B        |     |", type="table_row"),
        ],
        [
            make_block("p21_r0", "| STT | Hạng mục | Giá |", type="table_row"),
            make_block("p21_r1", "|     |          | 200 |", type="table_row"),
            make_block("p21_r2", "| 3   | C        | 300 |", type="table_row"),
        ],
        previous_page_num=20,
        next_page_num=21,
        document_state=DocumentState(active_table="table_01"),
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.ROW_CONTINUE
    assert action.action == Action.CONTINUE_ROW
    assert action.entity_type == EntityType.TABLE_ROW
    assert action.confidence >= 0.85
    assert action.target.table_id == "table_01"
    assert all(b.table_id == "table_01" and b.row_id for b in action.source_blocks)


def test_table_continuation_without_split_row_resolves_to_merge_table():
    context = _context(
        [
            make_block("p20_r0", "| STT | Hạng mục |", type="table_row"),
            make_block("p20_r1", "| 1   | A        |", type="table_row"),
        ],
        [
            make_block("p21_r0", "| STT | Hạng mục |", type="table_row"),
            make_block("p21_r1", "| 2   | B        |", type="table_row"),
        ],
        previous_page_num=20,
        next_page_num=21,
    )
    action = resolve_by_rule(context)
    assert action is not None
    assert action.relationship == Relationship.TABLE_CONTINUE
    # No `active_table` yet in document_state -> this is the *first* fusion.
    assert action.action == Action.MERGE_TABLE
    assert action.entity_type == EntityType.TABLE


def test_table_continuation_reuses_continue_table_once_active():
    context = _context(
        [
            make_block("p21_r0", "| STT | Hạng mục |", type="table_row"),
            make_block("p21_r1", "| 2   | B        |", type="table_row"),
        ],
        [
            make_block("p22_r0", "| STT | Hạng mục |", type="table_row"),
            make_block("p22_r1", "| 3   | C        |", type="table_row"),
        ],
        previous_page_num=21,
        next_page_num=22,
        document_state=DocumentState(active_table="table_01"),
    )
    action = resolve_by_rule(context)
    assert action.action == Action.CONTINUE_TABLE
    assert action.target.table_id == "table_01"


def test_case7_header_footer_blocks_excluded_from_boundary():
    previous_page = make_page(
        "doc1",
        12,
        [
            make_block(
                "p12_body", "Nội dung chính của trang mười hai.", bbox=(100, 300, 1000, 400)
            ),
            make_block(
                "p12_footer",
                "ABC CORPORATION - CONFIDENTIAL",
                type="footer",
                bbox=(100, 2270, 1000, 2310),
            ),
            make_block(
                "p12_pgnum", "Page 12 of 100", type="page_number", bbox=(700, 2310, 900, 2330)
            ),
        ],
    )
    next_page = make_page(
        "doc1",
        13,
        [
            make_block(
                "p13_header",
                "ABC CORPORATION - CONFIDENTIAL",
                type="header",
                bbox=(100, 20, 1000, 60),
            ),
            make_block(
                "p13_body", "Nội dung tiếp tục ở trang mười ba.", bbox=(100, 300, 1000, 400)
            ),
        ],
    )
    profile = detect_header_footer([previous_page, next_page])
    context = detect_boundary(previous_page, next_page, profile)

    for block in context.previous_blocks + context.next_blocks:
        assert block.type not in ("footer", "header", "page_number")
        assert "CONFIDENTIAL" not in block.text
        assert "Page 12 of 100" != block.text

    header_action = profile.action_for(next_page.blocks[0], next_page)
    assert header_action is not None
    assert header_action.action == Action.IGNORE_HEADER
    assert header_action.entity_type == EntityType.HEADER


def test_case8_ambiguous_boundary_is_not_resolved_by_rule():
    context = _context(
        [make_block("p10_b09", "Các bên đồng ý về nguyên tắc chung.")],
        [make_block("p11_b01", "hợp tác lâu dài trong tương lai.")],
    )
    action = resolve_by_rule(context)
    # Mixed signal here: previous ends with a full stop (new sentence) yet
    # next starts lowercase (looks like a continuation) — not conclusive.
    assert action is None
