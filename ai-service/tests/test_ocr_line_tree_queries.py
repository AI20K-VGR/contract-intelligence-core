"""Queries over the tree real OCR snapshots produce, not the tidy catalog one.

A scanned contract arrives as one node per line: "ĐIỀU 3. ..." is a one-line
CLAUSE heading and its "3.1."/"3.2." sub-clauses are UNNUMBERED_BLOCK children.
Body clauses that merely cite "Phụ lục SLA" sit beside the clause a question is
about. Each test pins a wrong answer seen on a live 20-page dossier.
"""

from __future__ import annotations

from app.reasoning.l1_retrieval import L1Retrieval
from app.reasoning.query import classify_ask
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures.catalog import make_envelope, make_node, make_page, make_record

DOSSIER = "d_ocr_line_tree"


def _stack() -> tuple[FourLayerReasoner, L1Retrieval, object, object]:
    n = [
        make_node("root", "SECTION", "Hợp đồng", "", order=0),
        make_node("a_name", "FIELD", "Tên đơn vị", "CÔNG TY CỔ PHẦN PHÚC THỊNH", parent_id="root",
                  order=1, structured_key="party_a", structured_value="CÔNG TY CỔ PHẦN PHÚC THỊNH"),
        make_node("b_name", "FIELD", "Tên đơn vị", "CÔNG TY TNHH CÔNG NGHỆ MINH HẢI", parent_id="root",
                  order=2, structured_key="party_b", structured_value="CÔNG TY TNHH CÔNG NGHỆ MINH HẢI"),
        make_node("d3", "CLAUSE", "ĐIỀU 3. TIẾN ĐỘ VÀ KẾ HOẠCH THỰC HIỆN",
                  "ĐIỀU 3. TIẾN ĐỘ VÀ KẾ HOẠCH THỰC HIỆN", parent_id="root", order=3, page=3),
        make_node("d3_1", "UNNUMBERED_BLOCK", "3.1. Thời gian triển khai",
                  "3.1. Thời gian triển khai dự kiến 08 tuần kể từ ngày hợp đồng có hiệu lực.",
                  parent_id="d3", order=4, page=3),
        make_node("d3_2", "UNNUMBERED_BLOCK", "3.2. Kế hoạch",
                  "3.2. Kế hoạch được chia thành các giai đoạn: khảo sát; triển khai; nghiệm thu.",
                  parent_id="d3", order=5, page=3),
        make_node("d4", "CLAUSE", "ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN",
                  "ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN", parent_id="root", order=6, page=3),
        make_node("d4_1", "UNNUMBERED_BLOCK", "4.1. Tổng giá trị hợp đồng",
                  "4.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng.",
                  parent_id="d4", order=7, page=3),
        make_node("d4_2", "UNNUMBERED_BLOCK", "4.2. Thanh toán",
                  "4.2. Bên A thanh toán 30% trong vòng 07 ngày làm việc kể từ ngày ký.",
                  parent_id="d4", order=8, page=3),
        make_node("d4_3", "UNNUMBERED_BLOCK", "4.3. Phương thức thanh toán",
                  "4.3. Thanh toán thực hiện bằng chuyển khoản vào tài khoản của Bên B.",
                  parent_id="d4", order=9, page=3),
        make_node("d8", "CLAUSE", "ĐIỀU 8. BẢO MẬT", "ĐIỀU 8. BẢO MẬT", parent_id="root", order=10, page=5),
        make_node("d8_3", "UNNUMBERED_BLOCK", "8.3. Bảo mật",
                  "8.3. Nghĩa vụ bảo mật có hiệu lực 03 năm, trừ khi pháp luật quy định thời hạn dài hơn.",
                  parent_id="d8", order=11, page=5),
        make_node("d16", "CLAUSE", "ĐIỀU 16. BẢO HÀNH", "ĐIỀU 16. BẢO HÀNH", parent_id="root", order=12, page=9),
        make_node("d16_3", "UNNUMBERED_BLOCK", "16.3. SLA",
                  "16.3. Mức độ ưu tiên sự cố và thời gian khắc phục thực hiện theo Phụ lục SLA.",
                  parent_id="d16", order=13, page=9),
        make_node("pl3", "SECTION", "PHỤ LỤC 03 - MỐC BÀN GIAO, NGHIỆM THU VÀ THANH TOÁN",
                  "PHỤ LỤC 03 - MỐC BÀN GIAO, NGHIỆM THU VÀ THANH TOÁN", parent_id="root", order=14, page=19),
        make_node("pl3_pay", "UNNUMBERED_BLOCK", "Thanh toán",
                  "Các khoản thanh toán được thực hiện trong vòng 10 ngày làm việc kể từ khi nhận đủ hồ sơ.",
                  parent_id="pl3", order=15, page=19),
    ]
    pages = [make_page(p, "\n".join(x.text for x in n if p in x.page_range)) for p in (1, 3, 5, 9, 19)]
    record = make_record(case_id="OCR-LINE-TREE", dossier=DOSSIER, pages=pages, nodes=n)
    store = InMemorySnapshotStore()
    store.put(record)
    gateway = ToolGateway(store)
    return FourLayerReasoner(gateway, None), L1Retrieval(gateway), make_envelope(dossier=DOSSIER), record


def _responsibility_stack() -> tuple[FourLayerReasoner, L1Retrieval, object, object]:
    stack, l1, envelope, record = _stack()
    record.nodes.extend(
        [
            make_node(
                "d6",
                "CLAUSE",
                "ĐIỀU 6. QUYỀN VÀ NGHĨA VỤ CỦA BÊN A",
                "ĐIỀU 6. QUYỀN VÀ NGHĨA VỤ CỦA BÊN A",
                parent_id="root",
                order=20,
                page=3,
            ),
            make_node(
                "d6_1",
                "UNNUMBERED_BLOCK",
                "6.1. Cung cấp tài liệu đúng thời hạn",
                "6.1. Cung cấp tài liệu đúng thời hạn; chịu trách nhiệm về tính hợp pháp của dữ liệu.",
                parent_id="d6",
                order=21,
                page=3,
            ),
            make_node(
                "d6_2",
                "UNNUMBERED_BLOCK",
                "6.2. Kiểm tra và phản hồi",
                "6.2. Tổ chức kiểm tra, phản hồi kết quả và thực hiện thanh toán theo đúng điều kiện hợp đồng.",
                parent_id="d6",
                order=22,
                page=3,
            ),
            make_node(
                "d6_3",
                "UNNUMBERED_BLOCK",
                "6.3. Không yêu cầu trái pháp luật",
                "6.3. Không yêu cầu Bên B thực hiện hành vi trái pháp luật hoặc sử dụng dữ liệu ngoài mục đích hợp đồng.",
                parent_id="d6",
                order=23,
                page=3,
            ),
            make_node(
                "d6_furniture",
                "UNNUMBERED_BLOCK",
                "HOP DONG KINH TE (tiep theo)",
                "HOP DONG KINH TE (tiep theo)",
                parent_id="d6",
                order=24,
                page=3,
            ),
        ]
    )
    record.active_nodes = None
    return stack, l1, envelope, record


def _ask(question: str) -> dict:
    stack, _, envelope, _ = _stack()
    task = {**classify_ask(question), "policy_flags": {"egress_allowed": False, "use_llm": False}}
    return stack.run(envelope, task)


def test_clause_lookup_returns_sub_clauses_not_just_the_heading():
    out = _ask("Điều 3 quy định gì?")
    assert "08 tuần" in str(out["answer"])
    assert "3.2." in str(out["answer"])


def test_asking_for_both_parties_names_both():
    task = classify_ask("Bên A và bên B là ai?")
    assert task["roles"] == ["A", "B"]
    answer = str(_ask("Bên A và bên B là ai?")["answer"])
    assert "PHÚC THỊNH" in answer
    assert "MINH HẢI" in answer


def test_progress_question_is_a_term_lookup_that_finds_the_clause():
    assert classify_ask("Tiến độ thực hiện hợp đồng là bao lâu?")["type"] == "lookup_term"
    assert "08 tuần" in str(_ask("Tiến độ thực hiện hợp đồng là bao lâu?")["answer"])


def test_payment_term_skips_clauses_that_only_mention_a_time_limit():
    _, l1, envelope, _ = _stack()
    task = classify_ask("Thời hạn thanh toán được quy định thế nào?")
    ids = [h.get("node_id") for h in l1.run(envelope, task)["hits"]]
    assert "d8_3" not in ids
    assert {"d4_2", "pl3_pay"} & set(ids)


def test_generic_payment_question_returns_a_bounded_payment_card():
    for question in ("Thông tin thanh toán?", "Thông tin trả tiền?"):
        task = classify_ask(question)
        assert task["type"] == "payment_card"
        result = _ask(question)
        assert "Chưa khớp intent" not in str(result["answer"])

    answer = _ask("Thông tin thanh toán?")
    text = str(answer["answer"])
    assert "Các đoạn liên quan" not in text
    assert "1.286.400.000" in text
    assert "chuyển khoản" in text
    assert "30%" in text
    assert "10 ngày làm việc" in text
    assert "03 năm" not in text
    assert len(answer.get("citations") or []) <= 6


def test_freeform_question_returns_grounded_evidence_instead_of_intent_hint():
    task = classify_ask("Các điều khoản về trách nhiệm là gì?")
    assert task["type"] == "unscoped"

    result = _ask("Các điều khoản về trách nhiệm là gì?")

    assert "Chưa khớp intent" not in str(result["answer"])
    assert result["review_state"] != "INSUFFICIENT_EVIDENCE"
    assert result["citations"]


def test_freeform_question_uses_llm_draft_when_policy_allows():
    class FakeLlm:
        def configured(self) -> bool:
            return True

        def complete_json(self, system: str, user: str, **kwargs):
            return {
                "answer": "Các đoạn được truy xuất nêu nghĩa vụ và mốc thực hiện liên quan; cần đối chiếu các citation kèm theo.",
                "citations": [{"node_id": "d4_2", "text_span": "Bên A thanh toán 30%"}],
                "sufficient": False,
                "legal_winner": False,
            }

    stack, _, envelope, _ = _stack()
    stack.l2.llm = FakeLlm()
    task = {
        **classify_ask("Các điều khoản về trách nhiệm là gì?"),
        "policy_flags": {"egress_allowed": True, "use_llm": True, "use_vector": False},
    }

    result = stack.run(envelope, task)

    assert "L2" in result["layers_used"]
    assert result["used_llm"] is True
    assert "Chưa khớp intent" not in str(result["answer"])
    assert "Các đoạn được truy xuất" in str(result["answer"])
    assert any(c.get("node_id") == "d4_2" for c in result["citations"])


def test_responsibility_question_expands_all_sibling_clauses():
    _, l1, envelope, _ = _responsibility_stack()
    task = {
        **classify_ask("Các điều khoản về trách nhiệm là gì?"),
        "policy_flags": {"egress_allowed": False, "use_llm": False},
    }

    result = l1.run(envelope, task)

    ids = {hit.get("node_id") for hit in result["hits"]}
    assert {"d6_1", "d6_2", "d6_3"} <= ids
    assert "d6_furniture" not in ids
    assert {"d6_1", "d6_2", "d6_3"} <= set(result["coverage_groups"])
    assert "d6_furniture" not in set(result["coverage_groups"])


def test_llm_answer_cannot_drop_retrieved_responsibility_siblings():
    class FakeLlm:
        def configured(self) -> bool:
            return True

        def complete_json(self, system: str, user: str, **kwargs):
            return {
                "answer": "Điều 6.1 yêu cầu cung cấp tài liệu đúng thời hạn.",
                "citations": [{"node_id": "d6_1", "text_span": "Cung cấp tài liệu đúng thời hạn"}],
                "sufficient": True,
                "legal_winner": False,
            }

    stack, _, envelope, _ = _responsibility_stack()
    stack.l2.llm = FakeLlm()
    task = {
        **classify_ask("Các điều khoản về trách nhiệm là gì?"),
        "policy_flags": {"egress_allowed": True, "use_llm": True, "use_vector": False},
    }

    result = stack.run(envelope, task)

    answer = str(result["answer"])
    assert "6.1" in answer and "6.2" in answer and "6.3" in answer
    assert {"d6_1", "d6_2", "d6_3"} <= {c.get("node_id") for c in result["citations"]}


def test_compare_keeps_named_body_and_annex_anchors_when_llm_cites_one_side():
    class FakeLlm:
        def configured(self) -> bool:
            return True

        def complete_json(self, system: str, user: str, **kwargs):
            return {
                "answer": "Điều 1 định nghĩa thuật ngữ.",
                "citations": [{"node_id": "d1", "text_span": "ĐIỀU 1"}],
                "sufficient": True,
                "legal_winner": False,
            }

    stack, _, envelope, record = _stack()
    record.nodes.extend(
        [
            make_node(
                "d1",
                "CLAUSE",
                "ĐIỀU 1. ĐỊNH NGHĨA VÀ GIẢI THÍCH",
                parent_id="root",
                order=30,
                page=3,
            ),
            make_node(
                "d1_1",
                "UNNUMBERED_BLOCK",
                "1.1. Hệ thống gồm phần mềm và các phụ lục.",
                parent_id="d1",
                order=31,
                page=3,
            ),
            make_node(
                "pl1",
                "SECTION",
                "PHỤ LỤC 01 - BẢNG THIẾT BỊ VÀ DỊCH VỤ",
                parent_id="root",
                order=32,
                page=19,
            ),
            make_node(
                "pl1_row",
                "UNNUMBERED_BLOCK",
                "| 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp |",
                parent_id="pl1",
                order=33,
                page=19,
            ),
        ]
    )
    record.active_nodes = None
    stack.l2.llm = FakeLlm()
    task = {
        **classify_ask("So sánh Điều 1 và Phụ lục 1"),
        "policy_flags": {"egress_allowed": True, "use_llm": True, "use_vector": False},
    }

    result = stack.run(envelope, task)

    cited = {citation.get("node_id") for citation in result["citations"]}
    assert "pl1" in cited
    assert {"d1", "d1_1"} & cited
    assert result["review_state"] == "NEEDS_REVIEW"


def test_compare_fallback_keeps_descriptive_body_and_annex_examples():
    class OneSidedLlm:
        def configured(self) -> bool:
            return True

        def complete_json(self, system: str, user: str, **kwargs):
            # The model saw both sides but cited only the body.  The
            # deterministic fallback must still choose a representative
            # definition and the first annex table row.
            return {
                "answer": "Điều 1 định nghĩa thuật ngữ.",
                "citations": [{"node_id": "d1_1", "text_span": "Hệ thống"}],
                "sufficient": True,
                "legal_winner": False,
            }

    stack, _, envelope, record = _stack()
    record.nodes.extend(
        [
            make_node(
                "d1",
                "CLAUSE",
                "ĐIỀU 1. ĐỊNH NGHĨA VÀ GIẢI THÍCH",
                parent_id="root",
                order=30,
                page=3,
            ),
            make_node(
                "d1_1",
                "UNNUMBERED_BLOCK",
                '1.1. "Hệ thống" là toàn bộ phần mềm và dịch vụ.',
                parent_id="d1",
                order=31,
                page=3,
            ),
            make_node(
                "d1_2",
                "UNNUMBERED_BLOCK",
                '1.2. "Ngày làm việc" là ngày không bao gồm thứ Bảy, Chủ Nhật và ngày nghỉ lễ.',
                parent_id="d1",
                order=32,
                page=3,
            ),
            make_node(
                "pl1",
                "SECTION",
                "PHỤ LỤC 01 - BẢNG KHỐI LƯỢNG, THIẾT BỊ VÀ DỊCH VỤ",
                parent_id="root",
                order=33,
                page=19,
            ),
            make_node(
                "pl1_header",
                "UNNUMBERED_BLOCK",
                "| STT | Hạng mục / Mô tả | DVT | SL | Đơn giá |",
                parent_id="pl1",
                order=34,
                page=19,
            ),
            make_node(
                "pl1_row11",
                "UNNUMBERED_BLOCK",
                "| 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp | bộ | 4 | 25.650.000 |",
                parent_id="pl1",
                order=35,
                page=19,
            ),
            make_node(
                "pl1_row12",
                "UNNUMBERED_BLOCK",
                "| 12 | Thiết bị lưu trữ và phụ kiện mở rộng | gói | 1 | 27.000.000 |",
                parent_id="pl1",
                order=36,
                page=19,
            ),
        ]
    )
    record.active_nodes = None
    stack.l2.llm = OneSidedLlm()
    task = {
        **classify_ask("So sánh Điều 1 và Phụ lục 1"),
        "policy_flags": {"egress_allowed": True, "use_llm": True, "use_vector": False},
    }

    result = stack.run(envelope, task)
    answer = str(result["answer"])

    assert "Ngày làm việc" in answer
    assert "| 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp |" in answer
    assert "Điều 1 tập trung vào định nghĩa và giải thích" in answer
    assert "Phụ lục 1 cung cấp thông tin chi tiết" in answer
    cited = {citation.get("node_id") for citation in result["citations"]}
    assert "d1_2" in cited
    assert "pl1_row11" in cited
    assert "pl1_row12" not in cited
    assert result["review_state"] == "NEEDS_REVIEW"


def test_body_vs_annex_compare_keeps_the_body_clause_on_topic():
    _, l1, envelope, _ = _stack()
    task = classify_ask("So sánh tiến độ thực hiện trong thân hợp đồng và phụ lục 03")
    assert task["type"] == "compare"
    ids = [h.get("node_id") for h in l1.run(envelope, task)["hits"]]
    assert "d3" in ids
    # Citing "Phụ lục SLA" does not make a warranty clause about progress.
    assert ids.index("d3") < ids.index("d16_3") if "d16_3" in ids else True


def test_llm_plan_gives_every_seed_a_turn_before_one_fills_the_budget():
    from app.reasoning.l2_plan import MAX_STEPS, L2Planner

    stack, _, envelope, record = _stack()
    rows = [
        make_node(f"pl3_row{i}", "UNNUMBERED_BLOCK", f"| M{i} |", f"| M{i} | mốc {i} | 10% |",
                  parent_id="pl3", order=20 + i, page=19)
        for i in range(1, 9)
    ]
    record.nodes.extend(rows)
    record.active_nodes = None
    l1 = {"hits": [{"node_id": "pl3"}, {"node_id": "d4"}]}
    plan = L2Planner(stack.l1.gateway, None)._evidence_plan({}, l1, False, envelope)
    ids = [step["args"]["node_id"] for step in plan]
    assert len(ids) <= MAX_STEPS
    # An 8-row annex table first in line must not crowd out the body clause.
    assert "d4_2" in ids
