from app.pipeline.grounding import repair_active_nodes
from app.reasoning.gold import adhoc_tasks
from app.reasoning.query import classify_ask
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures.catalog import all_cases, make_node, make_page, make_record


def _happy_stack():
    pack = all_cases()["HAPPY-001"]
    store = InMemorySnapshotStore()
    store.put(pack.record)
    return pack, FourLayerReasoner(ToolGateway(store), llm=None)


def test_happy_tasks_are_case_aware():
    tasks = {item["id"]: item for item in adhoc_tasks(all_cases()["HAPPY-001"].record.nodes)}
    assert tasks["T-MST"]["expected_state"] == "ANSWERED"
    assert tasks["T-ENTITY"]["expected_state"] == "NEEDS_REVIEW"
    assert tasks["T-PARA"]["kind"] == "probe"
    assert tasks["T-PARA"]["expected_state"] == "INSUFFICIENT_EVIDENCE"
    assert tasks["T-CASCADE"]["kind"] == "probe"
    assert tasks["T-CASCADE"]["expected_state"] == "INSUFFICIENT_EVIDENCE"


def test_happy_reasoning_returns_all_msts_and_conservative_entity_count():
    pack, stack = _happy_stack()
    mst = stack.run(pack.envelope, {"type": "lookup", "query": "MST trên hồ sơ là gì?"})
    assert mst["review_state"] == "ANSWERED"
    assert "0311111111" in mst["answer"] and "0322222222" in mst["answer"]
    assert len(mst["citations"]) == 2

    entity = stack.run(pack.envelope, {"type": "count_entity", "query": "Có bao nhiêu pháp nhân trong hợp đồng?"})
    assert entity["review_state"] == "NEEDS_REVIEW"
    assert "Có 2 pháp nhân" in entity["answer"]


def test_missing_term_and_relation_do_not_fall_back_to_entire_outline():
    pack, stack = _happy_stack()
    term = stack.run(
        pack.envelope,
        {"type": "lookup_term", "query": "How are working days defined versus payment after acceptance?"},
    )
    assert term["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert term["citations"] == []

    relation = stack.run(
        pack.envelope,
        {"type": "cascade", "query": "Nếu phụ lục đổi định nghĩa Ngày làm việc thì điều thanh toán bị ảnh hưởng thế nào?"},
    )
    assert relation["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert relation["citations"] == []


def test_bounded_document_overview_reports_missing_subject():
    pack, stack = _happy_stack()
    task = classify_ask("Hợp đồng số 01 nói về gì?")
    assert task["type"] == "document_overview"
    result = stack.run(pack.envelope, task)
    assert result["review_state"] == "NEEDS_REVIEW"
    assert "Công ty ABC" in result["answer"]
    assert "Công ty XYZ" in result["answer"]
    assert "đối tượng" in result["answer"]
    assert result["citations"]


def test_repair_view_excludes_fabricated_clause_without_mutating_raw_nodes():
    page = make_page(1, "Hợp đồng số 01. Bên A: Công ty ABC.")
    root = make_node("root", "SECTION", "Hợp đồng số 01", "Hợp đồng số 01", has_children=True)
    fake = make_node("fake_clause", "CLAUSE", "Điều 5.3", "Điều 5.3. Thanh toán trong 15 ngày.", parent_id="root")
    record = make_record(case_id="REPAIR", dossier="repair", pages=[page], nodes=[root, fake])
    active, issues = repair_active_nodes(record)
    assert [node.node_id for node in active] == ["root"]
    assert record.nodes[-1].node_id == "fake_clause"
    assert any(issue.code == "NODE_TEXT_UNGROUNDED" for issue in issues)


def test_relation_live_draft_cannot_drop_a_source():
    class PartialDraftLLM:
        def configured(self):
            return True

        def complete_json(self, system, user, *, strong=False):
            return {
                "answer": "Chá»‰ cÃ³ Phá»¥ lá»¥c 1.",
                "citations": [{"node_id": "a_5_pl1", "text_span": "Phá»¥ lá»¥c 1"}],
                "sufficient": True,
                "legal_winner": False,
            }

    from fixtures.catalog import load_case

    pack = load_case("HD-TONG-HOP")
    store = InMemorySnapshotStore()
    store.put(pack.record)
    stack = FourLayerReasoner(ToolGateway(store), llm=PartialDraftLLM())
    result = stack.run(
        pack.envelope,
        {"type": "compare", "query": "Dieu 5 lien quan den phu luc 1?"},
    )

    cited = {item.get("node_id") for item in result["citations"]}
    assert result["review_state"] == "NEEDS_REVIEW"
    assert {"a_5_pl1", "a_5_pl2"}.issubset(cited)
    assert "cl_5_body" in str(result["answer"])
