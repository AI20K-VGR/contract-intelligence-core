"""Regressions from live Q&A review, with different document values/labels."""

import pytest

from app.contracts.models import Citation, PageSnapshot, StructuralNode
from app.pipeline.citations import CitationResolver
from app.pipeline.outline import citation_for_node
from app.reasoning import answer_compose
from app.reasoning.l2_plan import L2Planner
from app.reasoning.query import QueryRouter
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures.eval_suite import synthetic_cases
from tests.test_answer_compose import LLM_FLAGS, FakeLLM
from tests.test_related_mocks import _page, _run


def _gateway(adapted):
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    return ToolGateway(store)


def test_same_phrase_on_page_one_of_two_files_keeps_the_correct_file_and_offsets():
    phrase = "20 máy quét mã vạch"
    pages = [
        PageSnapshot(
            page_revision_id="body-p1",
            page_number=1,
            source_file_id="body",
            text=f"Nội dung hợp đồng: {phrase}.",
            source_hash="a" * 64,
        ),
        PageSnapshot(
            page_revision_id="annex-p1",
            page_number=1,
            source_file_id="annex",
            text=phrase,
            source_hash="b" * 64,
            line_texts={"annex-line": phrase},
            line_bboxes={"annex-line": [0.1, 0.1, 0.9, 0.2]},
        ),
    ]
    node = StructuralNode(
        node_id="row",
        type="UNNUMBERED_BLOCK",
        raw_label=phrase,
        text=phrase,
        source_file_id="annex",
        page_revision_id="annex-p1",
        page_range=[1],
        source_line_ids=["annex-line"],
        bbox=[0.1, 0.1, 0.9, 0.2],
    )
    citation = citation_for_node([node], pages, node.node_id, text_span=phrase)
    assert citation["page_revision_id"] == "annex-p1"
    assert citation["char_start"] == 0
    assert CitationResolver(pages, nodes=[node]).verify(Citation.model_validate(citation)).valid


@pytest.mark.parametrize("number,last_amount", [("03", "275.000.000"), ("12", "890.000.000")])
def test_annex_evidence_keeps_late_rows_not_only_the_first_six(number, last_amount):
    adapted, _ = _run(
        f"table-{number}",
        [
            _page(1, ["ĐIỀU 1. PHẠM VI", "Cung cấp thiết bị phòng thí nghiệm."]),
            _page(
                2,
                [
                    f"PHỤ LỤC {number} - BẢNG GIÁ",
                    *[f"Hạng mục {i}: {i}.000.000 đồng." for i in range(1, 17)],
                    f"Hạng mục cuối: {last_amount} đồng.",
                ],
            ),
        ],
    )
    evidence = answer_compose.scoped_evidence(
        _gateway(adapted),
        adapted.envelope,
        {"query": f"Liệt kê toàn bộ hạng mục trong Phụ lục {number}."},
    )
    assert any(last_amount in e["text"] for e in evidence)
    assert any("Hạng mục 16" in e["text"] for e in evidence)


def test_reference_evidence_contains_the_target_clause_body():
    adapted, _ = _run(
        "qualified-reference",
        [
            _page(1, ["ĐIỀU 2. DẪN CHIẾU", "2.1. Thực hiện theo khoản 3 Điều 8."]),
            _page(
                2,
                [
                    "ĐIỀU 8. BÀN GIAO",
                    "8.1. Chuẩn bị hàng hóa.",
                    "8.3. Bàn giao trong vòng 19 ngày làm việc.",
                ],
            ),
        ],
    )
    evidence = answer_compose.scoped_evidence(
        _gateway(adapted),
        adapted.envelope,
        {"query": "Khoản 2.1 Điều 2 dẫn chiếu tới đâu và quy định gì?"},
    )
    assert any("19 ngày làm việc" in e["text"] for e in evidence)


def test_summary_covers_body_and_later_annexes_without_footers():
    adapted, _ = _run(
        "balanced-summary",
        [
            _page(
                1,
                [
                    "ĐIỀU 1. PHẠM VI",
                    "Cung cấp 45 bàn làm việc.",
                    "ĐIỀU 2. BẢO HÀNH",
                    "Bảo hành trong 36 tháng.",
                    "Trang 1/3",
                ],
            ),
            _page(2, ["PHỤ LỤC 04 - GIÁ", "Giá điều chỉnh 725.000.000 đồng."]),
            _page(3, ["PHỤ LỤC 09 - GIAO HÀNG", "Giao hàng trong 28 ngày."]),
        ],
    )
    evidence = answer_compose.evidence_from_outline(
        _gateway(adapted), adapted.envelope, adapted.record
    )
    text = "\n".join(e["text"] for e in evidence)
    assert all(value in text for value in ("45 bàn", "36 tháng", "725.000.000", "28 ngày"))
    assert "Trang 1/3" not in text


def test_evidence_expansion_does_not_override_member_permissions():
    adapted, _ = _run("scope-denied", [_page(1, ["ĐIỀU 1. GIÁ", "Giá là 90.000.000 đồng."])])
    denied = adapted.envelope.model_copy(
        update={"auth": adapted.envelope.auth.model_copy(update={"member_ids": ["outside-member"]})}
    )
    assert (
        answer_compose.scoped_evidence(_gateway(adapted), denied, {"query": "Điều 1 quy định gì?"})
        == []
    )


def test_comparing_named_annexes_keeps_the_unnamed_body_value():
    adapted, _ = _run(
        "three-values",
        [
            _page(1, ["ĐIỀU 4. GIÁ TRỊ", "Tổng giá trị hợp đồng là 810.000.000 đồng."]),
            _page(2, ["PHỤ LỤC 01 - GIÁ", "Tổng giá trị hợp đồng là 930.000.000 đồng."]),
            _page(3, ["PHỤ LỤC 03 - GIÁ", "Tổng giá trị hợp đồng là 875.000.000 đồng."]),
        ],
    )
    gateway = _gateway(adapted)
    llm = FakeLLM()
    QueryRouter(gateway.store, gateway, llm=llm).query(
        adapted.envelope,
        "So sánh giá trị hợp đồng chính, Phụ lục 01 và Phụ lục 03.",
        policy_flags=LLM_FLAGS,
    )
    assert all(
        amount in llm.prompts[-1] for amount in ("810.000.000", "930.000.000", "875.000.000")
    )


def test_bank_account_lookup_keeps_split_fields_inside_the_requested_party():
    adapted, _ = _run(
        "split-bank-fields",
        [
            _page(
                1,
                [
                    "BÊN A (BÊN MUA)",
                    "- Tài khoản: 1111111111",
                    "- Ngân hàng: Ngân hàng A",
                    "BÊN B (BÊN BÁN)",
                    "- Tài khoản: 2222222222",
                    "- Ngân hàng: Ngân hàng B",
                    "ĐIỀU 1. PHẠM VI",
                    "Cung cấp thiết bị.",
                ],
            ),
        ],
    )
    evidence = answer_compose.party_evidence(
        _gateway(adapted), adapted.envelope, "Số tài khoản ngân hàng của Bên B là bao nhiêu?"
    )
    text = "\n".join(item["text"] for item in evidence)
    assert "2222222222" in text
    assert "1111111111" not in text


def test_summary_composer_keeps_the_validated_selected_member_scope():
    pack = synthetic_cases()["SYN-001"]
    gateway = _gateway(pack)
    selected = next(n for n in pack.record.evidence_nodes() if n.node_id == "cl_5_body")
    hidden = next(
        n
        for n in pack.record.evidence_nodes()
        if n.text and n.node_id != selected.node_id and n.text not in selected.text
    )
    llm = FakeLLM()
    QueryRouter(gateway.store, gateway, llm=llm).query(
        pack.envelope,
        "Tóm tắt nội dung chính",
        {
            "type": "too_broad",
            "query": "Tóm tắt nội dung chính",
            "selected_member_ids": [selected.node_id],
        },
        policy_flags=LLM_FLAGS,
    )
    assert llm.prompts
    assert selected.text in llm.prompts[-1]
    assert hidden.text not in llm.prompts[-1]


def test_a_long_table_node_keeps_its_late_rows_in_composition_evidence():
    class TableGateway:
        def call(self, name, envelope, **kwargs):
            return {
                "type": "TABLE",
                "text": "\n".join(
                    f"| {i} | Hạng mục mô tả đủ dài để bảng vượt giới hạn đoạn văn | {i}.000.000 |"
                    for i in range(1, 31)
                ),
                "citation": {"node_id": "table"},
            }

    evidence = answer_compose.evidence_from_citations(TableGateway(), None, [{"node_id": "table"}])
    assert "| 29 |" in evidence[0]["text"]
    assert "| 30 |" in evidence[0]["text"]


def test_a_single_clause_question_does_not_require_two_comparison_citations():
    adapted, _ = _run(
        "one-clause-duration",
        [
            _page(1, ["ĐIỀU 8. BẢO MẬT", "8.3. Bảo mật trong 37 tháng sau khi chấm dứt."]),
        ],
    )
    target = next(n for n in adapted.record.evidence_nodes() if "37 tháng" in n.text)

    class OneClause(FakeLLM):
        def complete_json(self, system, user, **kwargs):
            return {
                "answer": "37 tháng sau khi chấm dứt.",
                "sufficient": True,
                "citations": [{"node_id": target.node_id, "text_span": target.text}],
            }

    gateway = _gateway(adapted)
    result = QueryRouter(gateway.store, gateway, llm=OneClause()).query(
        adapted.envelope,
        "Khoản 8.3 Điều 8 quy định bảo mật bao lâu?",
        {"type": "compare", "query": "Khoản 8.3 Điều 8 quy định bảo mật bao lâu?"},
        policy_flags=LLM_FLAGS,
    )
    assert result["answer"] == "37 tháng sau khi chấm dứt."


def test_oversized_context_is_bounded_and_cannot_claim_complete_coverage():
    evidence = [
        {
            "node_id": f"n{i}",
            "text": "x" * 2000,
            "path": "Large table",
            "citation": {"node_id": f"n{i}"},
        }
        for i in range(60)
    ]
    llm = FakeLLM()
    result = answer_compose.compose(llm, "Tóm tắt", evidence)
    assert result is not None
    assert result["sufficient"] is False
    assert len(llm.prompts[0]) <= answer_compose.PROMPT_CHAR_LIMIT


def test_an_explicitly_unanswerable_draft_does_not_get_unrelated_citations():
    adapted, _ = _run(
        "no-unrelated-cites",
        [
            _page(1, ["ĐIỀU 1. HÀNG HÓA", "Cung cấp 12 bàn làm việc."]),
        ],
    )
    node = next(n for n in adapted.record.evidence_nodes() if "12 bàn" in n.text)

    class Abstain(FakeLLM):
        def complete_json(self, system, user, **kwargs):
            return {
                "answer": "Hồ sơ không có thông tin để trả lời.",
                "citations": [],
                "sufficient": False,
                "legal_winner": False,
            }

    result = L2Planner(_gateway(adapted), Abstain()).run(
        adapted.envelope,
        {"type": "unscoped", "query": "Thủ đô của Nhật Bản là gì?"},
        {"hits": [{"node_id": node.node_id}]},
    )
    assert result["draft"]["citations"] == []
    assert result["draft"]["sufficient"] is False
