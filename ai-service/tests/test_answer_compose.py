"""Answer composer: L0/L1 evidence becomes a direct, cited model answer."""

from __future__ import annotations

from typing import Any

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
