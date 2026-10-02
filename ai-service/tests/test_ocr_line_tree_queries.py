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
        make_node("d4_2", "UNNUMBERED_BLOCK", "4.2. Thanh toán",
                  "4.2. Bên A thanh toán 30% trong vòng 07 ngày làm việc kể từ ngày ký.",
                  parent_id="d4", order=7, page=3),
        make_node("d8", "CLAUSE", "ĐIỀU 8. BẢO MẬT", "ĐIỀU 8. BẢO MẬT", parent_id="root", order=8, page=5),
        make_node("d8_3", "UNNUMBERED_BLOCK", "8.3. Bảo mật",
                  "8.3. Nghĩa vụ bảo mật có hiệu lực 03 năm, trừ khi pháp luật quy định thời hạn dài hơn.",
                  parent_id="d8", order=9, page=5),
        make_node("d16", "CLAUSE", "ĐIỀU 16. BẢO HÀNH", "ĐIỀU 16. BẢO HÀNH", parent_id="root", order=10, page=9),
        make_node("d16_3", "UNNUMBERED_BLOCK", "16.3. SLA",
                  "16.3. Mức độ ưu tiên sự cố và thời gian khắc phục thực hiện theo Phụ lục SLA.",
                  parent_id="d16", order=11, page=9),
        make_node("pl3", "SECTION", "PHỤ LỤC 03 - MỐC BÀN GIAO, NGHIỆM THU VÀ THANH TOÁN",
                  "PHỤ LỤC 03 - MỐC BÀN GIAO, NGHIỆM THU VÀ THANH TOÁN", parent_id="root", order=12, page=19),
        make_node("pl3_pay", "UNNUMBERED_BLOCK", "Thanh toán",
                  "Các khoản thanh toán được thực hiện trong vòng 10 ngày làm việc kể từ khi nhận đủ hồ sơ.",
                  parent_id="pl3", order=13, page=19),
    ]
    pages = [make_page(p, "\n".join(x.text for x in n if p in x.page_range)) for p in (1, 3, 5, 9, 19)]
    record = make_record(case_id="OCR-LINE-TREE", dossier=DOSSIER, pages=pages, nodes=n)
    store = InMemorySnapshotStore()
    store.put(record)
    gateway = ToolGateway(store)
    return FourLayerReasoner(gateway, None), L1Retrieval(gateway), make_envelope(dossier=DOSSIER), record


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
