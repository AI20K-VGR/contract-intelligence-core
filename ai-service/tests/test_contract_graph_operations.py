from __future__ import annotations

import pytest

from app.contracts.contract_graph import EdgeOp
from app.contracts.models import StructuralNode
from app.pipeline.contract_graph.address import canonical
from app.pipeline.contract_graph.builder import plan_edges
from app.pipeline.contract_graph.operations import (
    parse_operation,
    rejection_without_address,
    split_operation_units,
)
from app.pipeline.contract_graph.resolver import StructureIndex


def _targets(op) -> list[str]:
    return [canonical(a) for a in op.addresses]


@pytest.mark.parametrize(
    ("text", "op", "standard", "targets"),
    [
        ("Sửa đổi, bổ sung khoản 2 Điều 3 như sau:", EdgeOp.SUBSTITUTION, True, ["khoan 2 dieu 3"]),
        (
            "Bổ sung khoản 5 vào sau khoản 4 Điều 4 như sau:",
            EdgeOp.INSERTION,
            True,
            ["khoan 5 dieu 4"],
        ),
        (
            "Bãi bỏ khoản 3 và khoản 4 Điều 7.",
            EdgeOp.REPEAL,
            True,
            ["khoan 3 dieu 7", "khoan 4 dieu 7"],
        ),
        (
            'Thay cụm từ "A" bằng cụm từ "B" tại khoản 2 Điều 5',
            EdgeOp.SUBSTITUTION,
            True,
            ["khoan 2 dieu 5"],
        ),
        ('Bỏ cụm từ "X" tại điểm a khoản 1 Điều 2', EdgeOp.REPEAL, True, ["diem a khoan 1 dieu 2"]),
        ("Điều 4 được sửa đổi như sau:", EdgeOp.SUBSTITUTION, False, ["dieu 4"]),
        ("Khoản 2 Điều 8 không còn hiệu lực.", EdgeOp.REPEAL, False, ["khoan 2 dieu 8"]),
        ("Điều 5 không áp dụng đối với lô hàng 2.", EdgeOp.SCOPE_LIMIT, True, ["dieu 5"]),
        (
            "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7.",
            EdgeOp.REJECTION,
            False,
            ["khoan 2 dieu 7"],
        ),
    ],
)
def test_operation_templates(text, op, standard, targets):
    found = parse_operation(text)

    assert found is not None
    assert (found.op, found.standard) == (op, standard)
    assert _targets(found) == targets


def test_insertion_keeps_its_anchor_and_scope_limit_its_scope():
    insertion = parse_operation("Bổ sung khoản 5 vào sau khoản 4 Điều 4 như sau:")
    scope = parse_operation("Điều 5 không áp dụng đối với lô hàng 2.")

    assert canonical(insertion.addresses[0].insert_after) == "khoan 4 dieu 4"
    assert scope.scope_text == "lô hàng 2"


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("Điều chỉnh khoản 2 Điều 5 như sau:", "khoan 2 dieu 5"),
        ("Thay đổi Điều 7 của Hợp đồng như sau:", "dieu 7"),
        ("Khoản 2 Điều 5 được thay bằng nội dung sau:", "khoan 2 dieu 5"),
    ],
)
def test_contract_annex_verbs(text, target):
    found = parse_operation(text)

    assert found is not None
    assert (found.op, found.standard) == (EdgeOp.SUBSTITUTION, False)
    assert _targets(found) == [target]


def test_suffix_operation_targets():
    pair = parse_operation("Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3 như sau:")
    clause = parse_operation("Bổ sung khoản 5a vào sau khoản 5 Điều 18 như sau:")
    article = parse_operation("Bổ sung Điều 30a vào sau Điều 30")

    assert pair.op == EdgeOp.INSERTION
    assert _targets(pair) == ["diem d1 khoan 2 dieu 3", "diem d2 khoan 2 dieu 3"]
    assert _targets(clause) == ["khoan 5a dieu 18"]
    assert _targets(article) == ["dieu 30a"]
    units = split_operation_units(
        "5. Sửa đổi khoản 1 Điều 2.\n5a. Bãi bỏ khoản 3 Điều 2.\nd1) Bãi bỏ Điều 4."
    )
    assert [(u.label, u.level) for u in units] == [("5", "khoan"), ("5a", "khoan"), ("d1", "diem")]


@pytest.mark.parametrize(
    "text",
    [
        "Bên B có trách nhiệm sửa chữa hàng lỗi theo Điều 7.",
        "Giá được điều chỉnh theo chỉ số CPI tại Điều 4.",
        "Sau khi hoàn thành nghiệm thu theo Điều 6",
        "Bên A có quyền từ chối nhận hàng.",
        "Điều 8 của Hợp đồng không bị sửa đổi.",
        "Thay đổi số lượng hàng hóa theo bảng dưới đây.",
    ],
)
def test_exclusions_return_none(text):
    assert parse_operation(text) is None


def test_rejection_without_address_is_counted_not_parsed():
    assert rejection_without_address("Bên A có quyền từ chối nhận hàng.") is True
    assert (
        rejection_without_address("Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7.") is False
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bên B có trách nhiệm sửa chữa hàng hóa bị lỗi theo Điều 7.", None),
        ("Giá được điều chỉnh theo chỉ số CPI hằng quý tại Điều 4.", None),
        ("Bổ sung khoản 3 vào Điều 5 như sau:", EdgeOp.INSERTION),
        ("Bãi bỏ Điều 9 của Hợp đồng.", EdgeOp.REPEAL),
        ("Sau khi hoàn thành nghiệm thu theo Điều 6", None),
        ("Điều 5 không áp dụng đối với lô hàng 2.", EdgeOp.SCOPE_LIMIT),
    ],
)
def test_research_probe_sentences(text, expected):
    found = parse_operation(text)

    assert (found.op if found else None) == expected


@pytest.mark.parametrize(
    "text",
    [
        "1. Sửa đổi khoản 2 Điều 3 như sau:\n“2. Nội dung mới.”\n2. Bãi bỏ Điều 6.",
        "Sửa đổi, bổ sung một số điều như sau:\n1. Sửa đổi Điều 2.\na) Bỏ điểm a;\n  b) Thêm; c) x",
        "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7. Điều 5 không áp dụng; hết.",
        "Sửa đổi Điều 4 như sau: Bên B được bãi bỏ khoản 1 Điều 9.\n",
        "",
    ],
)
def test_units_offsets_roundtrip(text):
    units = split_operation_units(text)

    for unit in units:
        assert text[unit.char_start : unit.char_end] == unit.text
    if text.strip():
        assert units


def test_unlabelled_text_splits_on_sentence_ends():
    units = split_operation_units(
        "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7. Điều 5 không áp dụng đối với lô hàng 2."
    )

    assert [u.level for u in units] == [None, None]
    assert [parse_operation(u.text).op for u in units] == [EdgeOp.REJECTION, EdgeOp.SCOPE_LIMIT]


CONTAINER = (
    "2. Sửa đổi, bổ sung một số điểm của khoản 1 và khoản 2 Điều 3 như sau:\n"
    "a) Sửa đổi điểm c như sau:\n"
    "“c) Nội dung mới của điểm c.”\n"
    "b) Bổ sung điểm đ vào sau điểm d như sau:\n"
    "“đ) Nội dung của điểm đ mới.”"
)


def _index(source_text: str) -> tuple[StructuralNode, StructureIndex]:
    def node(node_id, label, parent=None, text="", file="f-body"):
        return StructuralNode(
            node_id=node_id,
            type="CLAUSE",
            raw_label=label,
            parent_id=parent,
            text=text,
            source_file_id=file,
        )

    nodes = [
        node("d3", "Điều 3"),
        node("d3k1", "1.", "d3"),
        node("d3k1c", "c)", "d3k1"),
        node("d3k2", "2.", "d3"),
        node("d3k2d", "d)", "d3k2"),
        node("src", "Điều 1", text=source_text, file="f-annex"),
    ]
    for order, item in enumerate(nodes):
        item.order = order
    index = StructureIndex.build(nodes, {"f-body": "body", "f-annex": "annex"})
    return nodes[-1], index


def test_container_unit_emits_no_edge_and_passes_parent_context():
    units = split_operation_units(CONTAINER)
    source, index = _index(CONTAINER)

    assert [(u.label, u.parent) for u in units] == [("2", None), ("a", 0), ("b", 0)]
    planned = plan_edges([source], index)
    assert [p.source_address for p in planned] == ["diem a khoan 2 dieu 1", "diem b khoan 2 dieu 1"]
    by_src = {p.source_address: p for p in planned}
    first = by_src["diem a khoan 2 dieu 1"]
    assert (first.op, first.target_address, first.target_node_id) == (
        EdgeOp.SUBSTITUTION,
        "diem c khoan 1 dieu 3",
        "d3k1c",
    )
    second = by_src["diem b khoan 2 dieu 1"]
    assert (second.op, second.target_address, second.target_node_id) == (
        EdgeOp.INSERTION,
        "diem đ khoan 2 dieu 3",
        "d3k2",
    )


def test_new_text_after_nhu_sau_is_not_parsed_as_operation():
    quoted = (
        "1. Sửa đổi khoản 2 Điều 3 như sau:\n"
        "“2. Bên A có quyền bãi bỏ khoản 1 Điều 9 và sửa đổi Điều 4 khi cần;\n"
        "a) Bãi bỏ Điều 6.”\n"
        "2. Bãi bỏ Điều 7."
    )
    inline = "Sửa đổi Điều 4 như sau: Bên B được bãi bỏ khoản 1 Điều 9. Điều 6 được sửa đổi."
    unquoted = "a) Sửa đổi Điều 4 như sau:\n1. Bên A bàn giao.\n2. Bên B nghiệm thu."

    ops = [parse_operation(u.text) for u in split_operation_units(quoted)]
    assert [(o.op, _targets(o)) for o in ops] == [
        (EdgeOp.SUBSTITUTION, ["khoan 2 dieu 3"]),
        (EdgeOp.REPEAL, ["dieu 7"]),
    ]
    assert "bãi bỏ khoản 1 Điều 9" in ops[0].new_text
    inline_units = split_operation_units(inline)
    assert len(inline_units) == 1
    assert _targets(parse_operation(inline_units[0].text)) == ["dieu 4"]
    unquoted_units = split_operation_units(unquoted)
    assert len(unquoted_units) == 1
    assert (
        parse_operation(unquoted_units[0].text).new_text
        == "1. Bên A bàn giao.\n2. Bên B nghiệm thu."
    )
    # same, when the announcing sentence carries no label of its own
    sentence = (
        "Sửa đổi Điều 4 như sau:\n1. Bên A bàn giao.\n2. Bên B nghiệm thu.\n3. Bãi bỏ Điều 9."
    )
    units = split_operation_units(sentence)
    assert [u.label for u in units] == [None, "3"]
    assert parse_operation(units[0].text).new_text == "1. Bên A bàn giao.\n2. Bên B nghiệm thu."


def test_unclosed_quote_does_not_swallow_the_next_items():
    # tt01-2022-bct: the new wording of item 3 never closes its quote
    text = (
        "3. Sửa đổi, bổ sung Điều 20 như sau:\n"
        "“Điều 20. Phương thức báo cáo\n"
        "Thương nhân báo cáo trực tuyến.\n"
        "4. Bổ sung Điều 20a dưới Điều 20 như sau:\n"
        "“Điều 20a. Chứng thực hợp đồng điện tử\n"
        "1. Bãi bỏ quy chế cũ tại Điều 9.\n"
        "a) Sửa đổi Điều 4.”\n"
        "5. Bãi bỏ Điều 28."
    )
    units = split_operation_units(text)

    assert [u.label for u in units] == ["3", "4", "5"]
    insertion = parse_operation(units[1].text)
    assert (insertion.op, insertion.standard) == (EdgeOp.INSERTION, False)
    assert _targets(insertion) == ["dieu 20a"]
    assert canonical(insertion.addresses[0].insert_after) == "dieu 20"


def test_d_stroke_target_preserved():
    found = parse_operation("Bổ sung điểm đ vào sau điểm d khoản 2 Điều 3")

    assert found.op == EdgeOp.INSERTION
    assert _targets(found) == ["diem đ khoan 2 dieu 3"]
    assert canonical(found.addresses[0].insert_after) == "diem d khoan 2 dieu 3"


def test_new_text_is_capped():
    found = parse_operation("Sửa đổi Điều 4 như sau:\n“" + "x" * 3000 + "”")

    assert len(found.new_text) == 2000


@pytest.mark.parametrize(
    ("text", "op", "targets"),
    [
        (
            "Thay thế cụm từ “A” bằng cụm từ “B” tại khoản 2 Điều 15; khoản 1 Điều 16; khoản 1 và 3 Điều 32.",
            EdgeOp.SUBSTITUTION,
            ["khoan 2 dieu 15", "khoan 1 dieu 16", "khoan 1 dieu 32", "khoan 3 dieu 32"],
        ),
        (
            "Bãi bỏ khoản 2 Điều 1; Điều 3; Điều 4 của Thông tư số 47/2014/TT-BCT.",
            EdgeOp.REPEAL,
            ["khoan 2 dieu 1", "dieu 3", "dieu 4"],
        ),
    ],
)
def test_address_list_continues_across_semicolons(text, op, targets):
    parsed = parse_operation(text)
    assert parsed is not None and parsed.op == op
    assert [canonical(a) for a in parsed.addresses] == targets


def test_semicolon_before_a_new_operation_still_splits():
    text = "Bãi bỏ khoản 2 Điều 3; sửa đổi Điều 5 như sau: “Điều 5. Nội dung mới.”"
    first = parse_operation(text)
    assert first is not None and first.op == EdgeOp.REPEAL
    assert [canonical(a) for a in first.addresses] == ["khoan 2 dieu 3"]
    ops = [parse_operation(u.text) for u in split_operation_units(text)]
    assert any(o is not None and o.op == EdgeOp.SUBSTITUTION for o in ops)
