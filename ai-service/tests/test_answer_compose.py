"""Answer composer: L0/L1 evidence becomes a direct, cited model answer."""

from __future__ import annotations

from typing import Any

import pytest

from app.contracts.models import SourceFile
from app.reasoning import answer_compose
from app.reasoning.query import QueryRouter
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures import envelope, mock_record

LLM_FLAGS = {"egress_allowed": True, "use_llm": True, "use_vector": False}


class FakeLLM:
    """Answers with the first evidence node it was shown, framed like a live model."""

    def __init__(self, answer: str = "Thanh toán trong 15 ngày.", wrap: bool = True) -> None:
        self.answer = answer
        self.wrap = wrap
        self.prompts: list[str] = []

    def configured(self) -> bool:
        return True

    def complete_json(self, system: str, user: str, **_: Any) -> dict[str, Any]:
        self.prompts.append(user)
        node_id = user.split("node_id: ", 1)[1].split("\n", 1)[0]
        return {
            "answer": self.answer,
            # Live models echo "[id]"; the composer must still match it.
            "citations": [{"node_id": f"[{node_id}]" if self.wrap else node_id, "text_span": "x"}],
            "sufficient": True,
        }


class BrokenLLM(FakeLLM):
    def complete_json(self, system: str, user: str, **_: Any) -> dict[str, Any]:
        raise TimeoutError("provider down")


def _router(llm: Any) -> QueryRouter:
    store = InMemorySnapshotStore()
    store.put(mock_record())
    return QueryRouter(store, ToolGateway(store), llm=llm)


def test_lookup_answer_is_written_by_the_model_with_valid_citations() -> None:
    llm = FakeLLM()
    result = _router(llm).query(
        envelope(), "Bên A thanh toán trong bao nhiêu ngày?", policy_flags=LLM_FLAGS
    )

    assert result["used_llm"] is True
    assert result["answer"] == "Thanh toán trong 15 ngày."
    assert result["citations"]
    known = {n.node_id for n in mock_record().evidence_nodes()}
    assert all(c["node_id"] in known for c in result["citations"])
    # An invented span falls back to the node's own text.
    assert all(c["text_span"] != "x" for c in result["citations"])
    assert "COMPOSE" in result["layers_used"]


def test_without_llm_policy_the_deterministic_answer_is_unchanged() -> None:
    off = {"egress_allowed": False, "use_llm": True}
    baseline = _router(None).query(
        envelope(), "Bên A thanh toán trong bao nhiêu ngày?", policy_flags=off
    )
    flagged_off = _router(FakeLLM()).query(
        envelope(), "Bên A thanh toán trong bao nhiêu ngày?", policy_flags=off
    )

    assert flagged_off["answer"] == baseline["answer"]
    assert flagged_off["used_llm"] is False


def test_provider_failure_keeps_the_deterministic_answer() -> None:
    baseline = _router(None).query(
        envelope(), "Bên A thanh toán trong bao nhiêu ngày?", policy_flags=LLM_FLAGS
    )
    result = _router(BrokenLLM()).query(
        envelope(), "Bên A thanh toán trong bao nhiêu ngày?", policy_flags=LLM_FLAGS
    )

    assert result["answer"] == baseline["answer"]
    assert result["citations"]


def test_citation_outside_the_evidence_is_dropped() -> None:
    evidence = [{"node_id": "a", "path": "A", "text": "alpha", "citation": {"node_id": "a"}}]

    class Stray(FakeLLM):
        def complete_json(self, system: str, user: str, **_: Any) -> dict[str, Any]:
            return {"answer": "x", "citations": [{"node_id": "zzz"}], "sufficient": True}

    assert answer_compose.compose(Stray(), "q", evidence) is None


def test_conflict_question_uses_stored_pair_relations() -> None:
    record = mock_record()
    a, b = [n.node_id for n in record.evidence_nodes() if n.text][:2]
    llm = FakeLLM("Có 1 xung đột.")
    task = {
        "type": "unscoped",
        "query": "chỉ ra xung đột",
        "pair_relations": [{"label": "CONFLICT", "node_a_id": a, "node_b_id": b}],
    }
    result = _router(llm).query(envelope(), "chỉ ra xung đột", task, policy_flags=LLM_FLAGS)

    assert result["answer"] == "Có 1 xung đột."
    assert "CONFLICT" in llm.prompts[-1]
    assert result["review_state"] == "NEEDS_REVIEW"


def test_conflict_composition_also_retrieves_sources_outside_the_stored_pairs(monkeypatch) -> None:
    from app.reasoning.stack import FourLayerReasoner

    llm = FakeLLM("Có các điều khoản cần đối chiếu.")
    store = InMemorySnapshotStore()
    record = mock_record()
    store.put(record)
    reasoner = FourLayerReasoner(ToolGateway(store), llm)
    extra = {
        "node_id": "extra",
        "path": "BB03",
        "text": "Thông báo sự cố sau 9 giờ.",
        "citation": {"node_id": "extra"},
    }
    monkeypatch.setattr(reasoner, "_compose_evidence", lambda *_: [extra])
    task = {
        "type": "unscoped",
        "query": "Chỉ ra mâu thuẫn",
        "pair_relations": [
            {"label": "CONFLICT", "node_a_id": "clause_5_3", "node_b_id": "field_value"}
        ],
        "policy_flags": LLM_FLAGS,
    }
    result = reasoner.run(envelope(), task)

    assert "BB03" in llm.prompts[-1]
    assert result["review_state"] == "NEEDS_REVIEW"


def test_explicit_document_code_retrieves_only_that_documents_nodes() -> None:

    record = mock_record()
    record.source_files = [
        SourceFile(file_id="bb01-file", filename="BB01_scan.pdf", role="annex"),
        SourceFile(file_id="bb02-file", filename="BB02_scan.pdf", role="annex"),
    ]
    record.nodes[0].source_file_id = "bb01-file"
    record.nodes[1].source_file_id = "bb02-file"
    store = InMemorySnapshotStore()
    store.put(record)
    evidence = answer_compose.document_evidence(
        ToolGateway(store), envelope(), "BB01 đã giao đủ chưa?"
    )

    assert [item["node_id"] for item in evidence] == ["sec_1"]


def test_high_risk_open_questions_use_scoped_composition_and_lexical_source_recall() -> None:
    from app.contracts.models import StructuralNode

    record = mock_record()
    record.nodes.append(
        StructuralNode(
            node_id="bb03-event",
            type="UNNUMBERED_BLOCK",
            raw_label="BB03",
            text="Sự cố phát hiện ngày 03/07 lúc 23:00; thông báo ngày 04/07 lúc 08:30.",
            order=20,
        )
    )
    store = InMemorySnapshotStore()
    store.put(record)
    gateway = ToolGateway(store)
    query = "Sự cố tháng 7 có quá hạn thông báo 6 giờ không?"

    assert answer_compose.needs_scoped_evidence({"query": query})
    evidence = answer_compose.lexical_evidence(gateway, envelope(), query)
    assert "bb03-event" in {item["node_id"] for item in evidence}
    assert answer_compose.needs_scoped_evidence(
        {"query": "Hai phiên bản PL06-A và PL06-B quy định SLA thế nào?"}
    )


def test_document_code_can_resolve_inside_a_combined_scan_page() -> None:
    from app.contracts.models import SourceFile
    from app.reasoning.stack import FourLayerReasoner

    record = mock_record()
    record.source_files = [
        SourceFile(file_id="combined-records", filename="scan-p41-43.pdf", role="annex")
    ]
    record.pages[0] = record.pages[0].model_copy(
        update={
            "source_file_id": "combined-records",
            "text": "BB01. Giao nhận một phần. Thực nhận 24/25 máy quét; một máy móp và thiếu bộ nguồn.",
            "line_texts": {
                "bb01-line": "BB01. Giao nhận một phần. Thực nhận 24/25 máy quét; một máy móp và thiếu bộ nguồn."
            },
            "source_hash": "a" * 64,
        }
    )
    store = InMemorySnapshotStore()
    store.put(record)

    evidence = answer_compose.document_evidence(
        ToolGateway(store), envelope(), "BB01 đã giao đủ máy quét chưa?"
    )

    assert [item["node_id"] for item in evidence] == ["page:page_1_rev_1"]
    assert "24/25" in evidence[0]["text"]

    reasoner = FourLayerReasoner(ToolGateway(store))
    result = reasoner.run(
        envelope(),
        {
            "type": "unscoped",
            "query": "BB01 đã giao đủ máy quét chưa?",
            "policy_flags": {"egress_allowed": False, "use_llm": False},
        },
    )
    assert "24/25" in result["answer"]
    assert result["citations"][0]["validation_status"] == "VALID"


def test_document_heading_outranks_a_contents_page_code_mention() -> None:
    from app.contracts.models import SourceFile

    record = mock_record()
    record.source_files = [
        SourceFile(file_id="combined-records", filename="scan-p01-p50.pdf", role="annex")
    ]
    target = record.pages[0].model_copy(
        update={
            "source_file_id": "combined-records",
            "text": "BB01. Giao nhận một phần. Bên B giao 24/25 máy quét.",
            "line_texts": {"bb01": "BB01. Giao nhận một phần. Bên B giao 24/25 máy quét."},
        }
    )
    contents = target.model_copy(
        update={
            "page_number": 34,
            "page_revision_id": "page_34_rev_1",
            "text": "Danh mục biên bản thực hiện có mã BB01, BB02, BB03 và TL01.",
            "line_texts": {
                "contents": "Danh mục biên bản thực hiện có mã BB01, BB02, BB03 và TL01."
            },
        }
    )
    record.pages = [contents, target]
    store = InMemorySnapshotStore()
    store.put(record)

    evidence = answer_compose.document_evidence(
        ToolGateway(store), envelope(), "BB01 đã giao đủ máy quét chưa?"
    )

    assert evidence[0]["node_id"] == f"page:{target.page_revision_id}"
    assert "24/25" in evidence[0]["text"]


@pytest.mark.parametrize("code", ["ZXQ17", "RPT/2026/007", "PRJ-QA-042", "NV-93", "X42"])
def test_document_identifiers_are_discovered_without_a_prefix_allowlist(code: str) -> None:
    record = mock_record()
    record.source_files = [
        SourceFile(file_id="custom", filename="attachment.pdf", document_number=code)
    ]
    record.nodes[0].source_file_id = "custom"
    store = InMemorySnapshotStore()
    store.put(record)
    evidence = answer_compose.document_evidence(
        ToolGateway(store), envelope(), f"{code} quy định gì?"
    )
    assert [item["node_id"] for item in evidence] == [record.nodes[0].node_id]


def test_document_code_matches_whole_identifier_not_a_longer_number() -> None:
    record = mock_record()
    record.source_files = [SourceFile(file_id="other", filename="ZXQ170_scan.pdf")]
    record.nodes[0].source_file_id = "other"
    store = InMemorySnapshotStore()
    store.put(record)
    assert answer_compose.document_evidence(ToolGateway(store), envelope(), "ZXQ17 ghi gì?") == []


def test_clause_references_and_dates_are_not_document_identifiers() -> None:
    assert (
        answer_compose.document_codes(
            "Điều 1, khoản 2, phụ lục 03, trang 5, ngày 15 tháng 10 năm 2026"
        )
        == set()
    )
    result = _router(None).query(envelope(), "Điều 1", policy_flags={"use_llm": False})
    assert "DOCUMENT_SOURCE" not in result.get("layers_used", [])


@pytest.mark.parametrize("query", ["Sự cố dữ liệu xử lý thế nào?", "Thanh lý và đối soát ra sao?"])
def test_topic_words_do_not_assign_fixture_document_codes(query: str) -> None:
    record = mock_record()
    record.source_files = [SourceFile(file_id="other", filename="BB03_TL01.pdf")]
    record.nodes[0].source_file_id = "other"
    store = InMemorySnapshotStore()
    store.put(record)
    assert answer_compose.document_evidence(ToolGateway(store), envelope(), query) == []
    assert answer_compose.expanded_query(query) == query


def test_named_document_with_llm_is_composed_instead_of_returned_as_raw_page() -> None:
    from app.reasoning.stack import FourLayerReasoner

    record = mock_record()
    record.source_files.append(SourceFile(file_id="custom-page", filename="scan.pdf"))
    record.pages[0] = record.pages[0].model_copy(
        update={
            "source_file_id": "custom-page",
            "text": "ZXQ17. Bên B chưa giao đủ thiết bị.",
            "line_texts": {"line": "ZXQ17. Bên B chưa giao đủ thiết bị."},
        }
    )
    store = InMemorySnapshotStore()
    store.put(record)
    llm = FakeLLM("Chưa giao đủ thiết bị.")
    result = FourLayerReasoner(ToolGateway(store), llm).run(
        envelope(),
        {
            "type": "unscoped",
            "query": "ZXQ17 đã giao đủ chưa?",
            "policy_flags": LLM_FLAGS,
        },
    )
    assert result["answer"] == "Chưa giao đủ thiết bị."
    assert "COMPOSE" in result["layers_used"]
    assert result["citations"]
    assert "ZXQ17. Bên B chưa giao đủ thiết bị." in llm.prompts[-1]


def test_named_document_without_llm_is_a_short_labelled_excerpt() -> None:
    from app.reasoning.stack import FourLayerReasoner

    record = mock_record()
    text = "ZXQ17. " + "Nội dung chứng minh. " * 100
    record.source_files.append(SourceFile(file_id="custom-page", filename="scan.pdf"))
    record.pages[0] = record.pages[0].model_copy(
        update={"source_file_id": "custom-page", "text": text, "line_texts": {"line": text}}
    )
    store = InMemorySnapshotStore()
    store.put(record)
    result = FourLayerReasoner(ToolGateway(store)).run(
        envelope(),
        {
            "type": "unscoped",
            "query": "ZXQ17 ghi gì?",
            "policy_flags": {"use_llm": False},
        },
    )
    assert result["answer"].startswith("Trích đoạn nguồn")
    assert len(result["answer"]) < 420
    assert result["used_llm"] is False


def test_document_title_recall_uses_actual_ocr_title_inside_combined_file() -> None:
    record = mock_record()
    record.source_files.append(SourceFile(file_id="combined", filename="scan-pages.pdf"))
    target = record.pages[0].model_copy(
        update={
            "source_file_id": "combined",
            "text": "BỘ HỒ SƠ\nZXQ17. Nhật ký chuyển đổi dữ liệu\nĐã chuyển 93 bản ghi.",
            "line_texts": {},
        }
    )
    other = target.model_copy(
        update={
            "page_revision_id": "other-page",
            "page_number": 2,
            "text": "ZXQ18. Biên bản kiểm tra\nCó dẫn chiếu nhật ký chuyển đổi dữ liệu ở cuối trang.",
        }
    )
    record.pages = [target, other]
    store = InMemorySnapshotStore()
    store.put(record)
    evidence = answer_compose.document_title_evidence(
        ToolGateway(store), envelope(), "Nhật ký chuyển đổi dữ liệu ghi nhận bao nhiêu bản ghi?"
    )
    assert evidence[0]["node_id"] == f"page:{target.page_revision_id}"
    assert "93" in evidence[0]["text"]


def test_title_based_table_question_sends_rows_to_composer() -> None:
    from app.reasoning.stack import FourLayerReasoner

    record = mock_record()
    record.source_files.append(SourceFile(file_id="service", filename="attachment.pdf"))
    record.pages[0] = record.pages[0].model_copy(
        update={
            "source_file_id": "service",
            "line_texts": {},
            "text": "PHỤ LỤC - SLA\n| Mức | Phản hồi |\n| P1 | 17 phút |\n| P4 | 3 ngày |",
        }
    )
    store = InMemorySnapshotStore()
    store.put(record)
    llm = FakeLLM("P1 phản hồi 17 phút; P4 phản hồi 3 ngày.")
    result = FourLayerReasoner(ToolGateway(store), llm).run(
        envelope(),
        {
            "type": "unscoped",
            "query": "SLA phản hồi P1 và P4 thế nào?",
            "policy_flags": LLM_FLAGS,
        },
    )
    assert "COMPOSE" in result["layers_used"]
    assert "| P1 | 17 phút |" in llm.prompts[-1]
    assert "| P4 | 3 ngày |" in llm.prompts[-1]


def test_bare_clause_lookup_stays_verbatim_but_a_clause_question_is_answered() -> None:
    assert not answer_compose.eligible({"type": "lookup_clause", "query": "điều 1"})
    assert answer_compose.eligible(
        {"type": "lookup_clause", "query": "Điều 5 quy định gì về nghiệm thu?"}
    )


def test_named_clause_is_found_by_its_number() -> None:
    record = mock_record()
    target = next(n for n in record.evidence_nodes() if (n.raw_label or "").strip())
    number = (target.raw_label or "").strip().split()[0].rstrip(".")
    if not number[:1].isdigit():
        return
    assert target.node_id in answer_compose.referenced_nodes(record, f"khoản {number} là gì?")


def test_expansion_reaches_the_dispute_clause_wording() -> None:
    assert "tranh chấp" in answer_compose.expanded_query("Có trọng tài quốc tế không?")


def test_comparison_citing_sub_clauses_of_both_headings_keeps_the_model_sentence() -> None:
    # Live run: L1 anchors the two headings, the model quotes the body line under
    # each, wrapped as "[id]". The two-source check read parent links backwards
    # and the bracketed ids never matched, so every comparison fell back to a list.
    from app.reasoning.stack import FourLayerReasoner
    from tests.test_related_mocks import _page, _run

    adapted, _job = _run(
        "compare-children",
        [
            _page(1, ["ĐIỀU 1. GIÁ TRỊ HỢP ĐỒNG", "Tổng giá trị hợp đồng là 1.000.000.000 đồng."]),
            _page(2, ["PHỤ LỤC 01 - BẢNG GIÁ", "Tổng giá trị hợp đồng là 1.200.000.000 đồng."]),
        ],
    )
    nodes = [n for n in adapted.record.evidence_nodes() if not n.node_id.startswith("ai2-root")]
    by_id = {n.node_id: n for n in nodes}
    children = [n for n in nodes if n.parent_id in by_id]
    headings = [by_id[c.parent_id].node_id for c in children]
    assert len(set(headings)) == 2, "fixture must give each heading a body line"

    class Model(FakeLLM):
        def complete_json(self, system: str, user: str, **_: Any) -> dict[str, Any]:
            return {
                "answer": "Mô hình: thân 1 tỷ, phụ lục 1,2 tỷ.",
                "citations": [
                    {"node_id": f"[{c.node_id}]", "text_span": c.text[:20]} for c in children
                ],
                "sufficient": False,
                "legal_winner": False,
            }

    store = InMemorySnapshotStore()
    store.put(adapted.record)
    reasoner = FourLayerReasoner(ToolGateway(store), Model())
    reasoner.l1.run = lambda envelope, task: {
        "hits": [{"node_id": h, "citation": {"node_id": h}} for h in headings],
        "anchor_ids": headings,
        "outline_ids": [{"node_id": h} for h in headings],
        "blocked": False,
        "relations": [],
        "relation_edges": [],
        "relation_issues": [],
        "retrieval_trace": {},
    }
    result = reasoner.run(
        adapted.envelope,
        {"type": "compare", "query": "So sánh Điều 1 và Phụ lục 01", "policy_flags": LLM_FLAGS},
    )

    assert "Mô hình:" in str(result.get("answer"))
