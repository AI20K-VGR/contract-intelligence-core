from __future__ import annotations

import pytest

from app.pipeline.contract_graph.builder import plan_edges
from app.pipeline.contract_graph.documents import named_document
from app.pipeline.contract_graph.resolver import Status
from tests.test_contract_graph_operations import _index


@pytest.mark.parametrize(
    ("text", "doc"),
    [
        ("Sửa đổi, bổ sung Thông tư số 156/2013/TT-BTC ngày 06/11/2013 như sau:", "156/2013/tt-btc"),
        ("Bãi bỏ Điều 8 Thông tư 47/2014/TT-BCT.", "47/2014/tt-bct"),
        ("Nghị định số 37/2015/NĐ-CP được sửa đổi như sau:", "37/2015/nđ-cp"),
        ("sửa đổi khoản 2 Điều 5 của Hợp đồng số: 15/2023/HĐKT như sau:", "15/2023/hđkt"),
        ("Sửa đổi điểm a khoản 8 Điều 11 như sau:", None),
        ("Sửa đổi khoản 2 Điều 5 của Hợp đồng này như sau:", None),
        ("Thay thế cụm từ “Thông tư số 1/2020/TT-BTC” bằng cụm từ “B” tại Điều 3.", None),
    ],
)
def test_named_document(text, doc):
    assert named_document(text) == doc


CONTAINER = (
    "1. Sửa đổi, bổ sung Thông tư số 156/2013/TT-BTC như sau:\n"
    "a) Sửa đổi điểm c khoản 1 Điều 3 như sau:\n"
    "“c) Nội dung mới của điểm c.”"
)


def test_operation_inheriting_a_foreign_document_plans_no_edge():
    source, index = _index(CONTAINER)
    [plan] = plan_edges([source], index, known_documents={"219/2013/tt-btc"})
    assert plan.status == Status.FOREIGN_DOCUMENT
    assert plan.target_node_id is None


def test_operation_on_a_known_document_resolves():
    source, index = _index(CONTAINER)
    [plan] = plan_edges([source], index, known_documents={"156/2013/tt-btc"})
    assert plan.status == Status.UNIQUE
    assert plan.target_node_id == "d3k1c"


def test_unknown_identities_block_named_documents():
    # direction B: no identity known for the dossier ⇒ a named document is never assumed to be it
    source, index = _index(CONTAINER)
    [plan] = plan_edges([source], index)
    assert plan.status == Status.FOREIGN_DOCUMENT


def test_operation_naming_no_document_keeps_resolving():
    source, index = _index("Sửa đổi điểm c khoản 1 Điều 3 như sau:\n“c) Nội dung mới.”")
    [plan] = plan_edges([source], index)
    assert plan.status == Status.UNIQUE


def test_own_document_named_in_the_sentence_wins_over_the_heading():
    text = (
        "1. Sửa đổi, bổ sung Thông tư số 156/2013/TT-BTC như sau:\n"
        "a) Sửa đổi điểm c khoản 1 Điều 3 Thông tư số 219/2013/TT-BTC như sau:\n"
        "“c) Nội dung mới.”"
    )
    source, index = _index(text)
    [plan] = plan_edges([source], index, known_documents={"219/2013/tt-btc"})
    assert plan.status == Status.UNIQUE
